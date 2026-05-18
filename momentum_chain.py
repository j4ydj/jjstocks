#!/usr/bin/env python3
"""
Momentum Chain Finder
=====================
1. Rank universe by short-term realized volatility → top N focus list.
2. For each focus ticker, map upstream/downstream drivers across:
   - MACRO: indices, sector ETFs, rates, vol, commodities
   - MICRO: peers, volume, trader attention, recent catalysts
3. Estimate lead/lag and build an ordered event chain for planning.

Not a catch-all trade scanner — depth on the movers that matter right now.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Macro basket (always checked for lead/lag vs focus names)
# ---------------------------------------------------------------------------

MACRO_NODES = {
    "SPY": "US broad market",
    "QQQ": "Nasdaq / growth",
    "IWM": "Small caps",
    "TLT": "Long bonds / rates",
    "UUP": "US dollar",
    "GLD": "Gold",
    "USO": "Crude oil",
    "HYG": "High-yield credit",
    "^VIX": "Equity volatility",
    "XLK": "Technology sector",
    "XLF": "Financials sector",
    "XLE": "Energy sector",
    "XLV": "Healthcare sector",
    "XBI": "Biotech sector",
    "SMH": "Semiconductors",
    "ARKK": "Innovation / speculative growth",
}

SECTOR_TO_ETF = {
    "technology": "XLK",
    "communication services": "XLC",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "financial services": "XLF",
    "financial": "XLF",
    "healthcare": "XLV",
    "energy": "XLE",
    "basic materials": "XLB",
    "industrials": "XLI",
    "utilities": "XLU",
    "real estate": "XLRE",
}

# Known supply-chain / thematic links (upstream → focus → downstream)
THEMATIC_LINKS: Dict[str, Dict[str, List[str]]] = {
    "NVDA": {
        "upstream_macro": ["SMH", "SOXX", "QQQ"],
        "upstream_micro": ["AMD", "AVGO", "TSM", "ASML"],
        "downstream_micro": ["MSFT", "GOOGL", "META", "AMZN", "ORCL"],
    },
    "AMD": {
        "upstream_macro": ["SMH", "XLK"],
        "upstream_micro": ["NVDA", "INTC", "TSM"],
        "downstream_micro": ["DELL", "HPQ"],
    },
    "COIN": {
        "upstream_macro": ["ARKK", "QQQ"],
        "upstream_micro": ["MSTR", "MARA", "RIOT", "BTC-USD"],
        "downstream_micro": ["HOOD", "SQ"],
    },
    "MSTR": {
        "upstream_macro": ["ARKK"],
        "upstream_micro": ["BTC-USD", "COIN"],
        "downstream_micro": ["MARA", "RIOT"],
    },
    "TSLA": {
        "upstream_macro": ["QQQ", "XLY"],
        "upstream_micro": ["RIVN", "LCID", "NIO"],
        "downstream_micro": ["PANW", "ALB", "LTHM"],
    },
    "RKLB": {
        "upstream_macro": ["ARKK", "IWM"],
        "upstream_micro": ["ASTS", "LUNR", "SPCE"],
        "downstream_micro": ["PL", "BA"],
    },
    "PLTR": {
        "upstream_macro": ["XLK", "QQQ"],
        "upstream_micro": ["SNOW", "AI", "PATH"],
        "downstream_micro": ["LMT", "RTX"],
    },
    "GME": {
        "upstream_macro": ["IWM", "ARKK"],
        "upstream_micro": ["AMC", "BB", "KOSS"],
        "downstream_micro": [],
    },
    "SMCI": {
        "upstream_macro": ["SMH", "XLK"],
        "upstream_micro": ["NVDA", "AMD", "DELL"],
        "downstream_micro": ["ANET", "VRT"],
    },
}

MOVE_THRESHOLD_PCT = 1.5
VOL_LOOKBACK_DAYS = 10
CORR_LOOKBACK_DAYS = int(os.getenv("CORR_LOOKBACK_DAYS", "60"))
MAX_LAG_DAYS = 3
MIN_CORR_ABS = float(os.getenv("MIN_CORR_ABS", "0.55"))
MIN_CORR_PVALUE = float(os.getenv("MIN_CORR_PVALUE", "0.05"))
DEFAULT_TOP_N = 10
MIN_DOLLAR_VOLUME = float(os.getenv("MIN_DOLLAR_VOLUME", "15000000"))


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class VolatilePick:
    ticker: str
    rank: int
    vol_annualized_pct: float
    atr_pct: float
    return_5d_pct: float
    return_1d_pct: float
    volume_ratio: float
    composite_score: float = 0.0
    vol_expansion: float = 1.0
    last_price: float = 0.0


@dataclass
class ChainLink:
    node: str
    layer: str          # macro | micro
    direction: str      # upstream | downstream | peer
    role: str           # human label
    corr_21d: float     # Pearson r over CORR_LOOKBACK_DAYS (field name kept for compat)
    lead_lag_days: int  # +N = node leads focus by N days; -N = focus leads
    move_1d_pct: float
    move_5d_pct: float
    last_price: float = 0.0
    note: str = ""
    corr_pvalue: float = 1.0
    sample_n: int = 0
    lag_hit_rate: Optional[float] = None
    lag_hit_n: int = 0
    corr_significant: bool = False
    regime_break: bool = False


@dataclass
class ChainEvent:
    date: str
    node: str
    layer: str
    move_pct: float
    direction: str      # up | down
    relation: str       # focus | upstream | downstream | macro


@dataclass
class MomentumChain:
    focus: VolatilePick
    links: List[ChainLink]
    events: List[ChainEvent]
    narrative: List[str]
    scan_time: str


@dataclass
class MomentumScanResult:
    scan_time: str
    universe_size: int
    top_volatile: List[VolatilePick]
    chains: List[MomentumChain]


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

def load_scan_universe() -> List[str]:
    from universe import load_scan_universe as _load
    return _load()


def min_dollar_volume(df: pd.DataFrame, window: int = 20) -> float:
    if df is None or len(df) < window + 1:
        return 0.0
    dv = df["Close"].iloc[-window - 1:-1] * df["Volume"].iloc[-window - 1:-1]
    return float(dv.mean()) if len(dv) else 0.0


# ---------------------------------------------------------------------------
# Volatility ranking
# ---------------------------------------------------------------------------

def _normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df


def realized_vol_pct(close: pd.Series, window: int = VOL_LOOKBACK_DAYS) -> Optional[float]:
    if close is None or len(close) < window + 1:
        return None
    rets = np.log(close.iloc[-window - 1:] / close.iloc[-window - 1:].shift(1)).dropna()
    if len(rets) < window - 1:
        return None
    return float(rets.std() * np.sqrt(252) * 100)


def vol_expansion_ratio(close: pd.Series, short: int = 10, long: int = 60) -> float:
    """Short-term vol / longer baseline; >1 means vol picking up."""
    v_short = realized_vol_pct(close, min(short, len(close) - 2))
    v_long = realized_vol_pct(close, min(long, len(close) - 2))
    if not v_short or not v_long or v_long <= 0:
        return 1.0
    return float(v_short / v_long)


def gap_quality_penalty(df: pd.DataFrame) -> float:
    """Demote single-day gap spikes without volume confirmation."""
    if df is None or len(df) < 22:
        return 1.0
    r1 = abs((df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100)
    vol_avg = df["Volume"].iloc[-21:-1].mean()
    vol_ratio = float(df["Volume"].iloc[-1] / vol_avg) if vol_avg and vol_avg > 0 else 1.0
    if r1 > 7.0 and vol_ratio < 1.15:
        return 0.55
    if r1 > 5.0 and vol_ratio < 1.0:
        return 0.75
    return 1.0


def composite_vol_score(vol: float, atr: float, expansion: float, penalty: float = 1.0) -> float:
    raw = 0.45 * vol + 0.35 * (atr * 4.0) + 0.20 * (min(expansion, 3.0) * 25.0)
    return raw * penalty


def atr_pct(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df is None or len(df) < period + 1:
        return None
    h = df["High"].values[-period:]
    l = df["Low"].values[-period:]
    c_prev = df["Close"].values[-period - 1:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - c_prev), np.abs(l - c_prev)))
    atr = float(np.mean(tr))
    price = float(df["Close"].iloc[-1])
    if price <= 0:
        return None
    return atr / price * 100


def rank_by_volatility(
    tickers: List[str],
    top_n: int = DEFAULT_TOP_N,
    prefetched: Optional[Dict[str, pd.DataFrame]] = None,
    min_dv: float = MIN_DOLLAR_VOLUME,
) -> Tuple[List[VolatilePick], Dict[str, pd.DataFrame]]:
    """Return top N by 10-day realized vol and price history dict."""
    data = prefetched or _bulk_download(tickers)
    picks: List[VolatilePick] = []

    for ticker, df in data.items():
        if df is None or len(df) < VOL_LOOKBACK_DAYS + 5:
            continue
        if min_dv > 0 and min_dollar_volume(df) < min_dv:
            continue
        vol = realized_vol_pct(df["Close"], VOL_LOOKBACK_DAYS)
        if vol is None or vol <= 0:
            continue
        atr = atr_pct(df) or 0.0
        expansion = vol_expansion_ratio(df["Close"])
        penalty = gap_quality_penalty(df)
        composite = composite_vol_score(vol, atr, expansion, penalty)
        c = df["Close"]
        r5 = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0.0
        r1 = (c.iloc[-1] / c.iloc[-2] - 1) * 100 if len(c) >= 2 else 0.0
        vol_avg = df["Volume"].iloc[-21:-1].mean() if len(df) >= 22 else df["Volume"].mean()
        vol_ratio = float(df["Volume"].iloc[-1] / vol_avg) if vol_avg and vol_avg > 0 else 1.0

        picks.append(
            VolatilePick(
                ticker=ticker,
                rank=0,
                vol_annualized_pct=round(vol, 1),
                atr_pct=round(atr, 2),
                return_5d_pct=round(r5, 2),
                return_1d_pct=round(r1, 2),
                volume_ratio=round(vol_ratio, 2),
                composite_score=round(composite, 1),
                vol_expansion=round(expansion, 2),
                last_price=round(float(c.iloc[-1]), 2),
            )
        )

    picks.sort(key=lambda p: p.composite_score, reverse=True)
    top = picks[:top_n]
    for i, p in enumerate(top, 1):
        p.rank = i
    focus_data = {p.ticker: data[p.ticker] for p in top if p.ticker in data}
    return top, focus_data


def _bulk_download(tickers: List[str], extra: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
    syms = list(dict.fromkeys((tickers or []) + (extra or [])))
    out: Dict[str, pd.DataFrame] = {}
    if not syms:
        return out
    try:
        raw = yf.download(
            syms,
            period="6mo",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return out
        if isinstance(raw.columns, pd.MultiIndex):
            for t in raw.columns.get_level_values(0).unique():
                df_t = _normalize_index(raw[t].copy())
                if df_t is not None and len(df_t) >= VOL_LOOKBACK_DAYS + 5 and "Close" in df_t.columns:
                    out[str(t)] = df_t
        elif len(syms) == 1 and "Close" in raw.columns:
            out[syms[0]] = _normalize_index(raw.copy())
    except Exception as e:
        logger.warning("Bulk download failed: %s", e)
    return out


# ---------------------------------------------------------------------------
# Lead/lag & correlation
# ---------------------------------------------------------------------------

def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change(fill_method=None).dropna()


def lead_lag_corr(
    focus_rets: pd.Series,
    node_rets: pd.Series,
    max_lag: int = MAX_LAG_DAYS,
) -> Tuple[float, int]:
    """
    Find lag that maximizes |correlation|.
    Positive lag => node leads focus (node moves first).
    """
    def _col(s: pd.Series, name: str) -> pd.Series:
        out = s.squeeze() if hasattr(s, "squeeze") else s
        if isinstance(out, pd.DataFrame):
            out = out.iloc[:, 0]
        return pd.Series(out.values, index=out.index, name=name)

    aligned = pd.concat([_col(focus_rets, "f"), _col(node_rets, "n")], axis=1).dropna()
    if len(aligned) < 12:
        return 0.0, 0

    f = aligned["f"].values
    n = aligned["n"].values
    best_corr, best_lag = 0.0, 0

    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            if len(f) <= lag:
                continue
            a, b = n[:-lag], f[lag:]
        elif lag < 0:
            k = -lag
            if len(f) <= k:
                continue
            a, b = n[k:], f[:-k]
        else:
            a, b = n, f
        if len(a) < 8:
            continue
        c = np.corrcoef(a, b)[0, 1]
        if np.isnan(c):
            continue
        if abs(c) > abs(best_corr):
            best_corr, best_lag = float(c), lag

    return best_corr, best_lag


def _sector_etf(ticker: str) -> Optional[str]:
    try:
        info = yf.Ticker(ticker).info or {}
        sector = (info.get("sector") or "").lower().strip()
        for key, etf in SECTOR_TO_ETF.items():
            if key in sector:
                return etf
    except Exception:
        pass
    return None


def _candidate_nodes(focus: str) -> List[Tuple[str, str, str]]:
    """(symbol, layer, direction) candidates to test."""
    nodes: List[Tuple[str, str, str]] = []

    for sym, desc in MACRO_NODES.items():
        nodes.append((sym, "macro", "upstream"))

    thematic = THEMATIC_LINKS.get(focus.upper(), {})
    for sym in thematic.get("upstream_macro", []):
        nodes.append((sym, "macro", "upstream"))
    for sym in thematic.get("upstream_micro", []):
        nodes.append((sym, "micro", "upstream"))
    for sym in thematic.get("downstream_micro", []):
        nodes.append((sym, "micro", "downstream"))

    try:
        import peer_discovery
        auto = peer_discovery.discover_peers(focus)
        for sym in auto.get("upstream_macro", []):
            nodes.append((sym, "macro", "upstream"))
        for sym in auto.get("upstream_micro", []):
            nodes.append((sym, "micro", "upstream"))
        for sym in auto.get("downstream_micro", []):
            nodes.append((sym, "micro", "downstream"))
    except Exception as e:
        logger.debug("peer_discovery: %s", e)

    etf = _sector_etf(focus)
    if etf and etf not in MACRO_NODES:
        nodes.append((etf, "macro", "upstream"))

    # Dedupe preserving order
    seen = set()
    unique: List[Tuple[str, str, str]] = []
    for item in nodes:
        sym = item[0].upper()
        if sym == focus.upper() or sym in seen:
            continue
        seen.add(sym)
        unique.append((sym, item[1], item[2]))
    return unique


# ---------------------------------------------------------------------------
# Event chain
# ---------------------------------------------------------------------------

def _significant_moves(
    ticker: str,
    df: pd.DataFrame,
    layer: str,
    relation: str,
    threshold: float = MOVE_THRESHOLD_PCT,
    last_n_days: int = 10,
) -> List[ChainEvent]:
    events: List[ChainEvent] = []
    if df is None or len(df) < 3:
        return events
    tail = df.tail(last_n_days + 1)
    for i in range(1, len(tail)):
        prev = float(tail["Close"].iloc[i - 1])
        curr = float(tail["Close"].iloc[i])
        if prev <= 0:
            continue
        move = (curr / prev - 1) * 100
        if abs(move) < threshold:
            continue
        dt = tail.index[i]
        date_s = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        events.append(
            ChainEvent(
                date=date_s,
                node=ticker,
                layer=layer,
                move_pct=round(move, 2),
                direction="up" if move > 0 else "down",
                relation=relation,
            )
        )
    return events


def build_chain(
    pick: VolatilePick,
    focus_df: pd.DataFrame,
    node_data: Dict[str, pd.DataFrame],
) -> MomentumChain:
    focus = pick.ticker.upper()
    focus_rets = daily_returns(focus_df["Close"]).tail(CORR_LOOKBACK_DAYS)

    links: List[ChainLink] = []
    for sym, layer, direction in _candidate_nodes(focus):
        df = node_data.get(sym)
        if df is None or len(df) < CORR_LOOKBACK_DAYS + 5:
            continue
        node_rets = daily_returns(df["Close"]).tail(CORR_LOOKBACK_DAYS)
        corr, lag = lead_lag_corr(focus_rets, node_rets)
        from chain_stats import (
            aligned_returns,
            corr_pvalue,
            corr_significant,
            correlation_regime_break,
            lead_lag_hit_rate,
        )

        aligned = aligned_returns(focus_rets, node_rets)
        n = len(aligned)
        pval = corr_pvalue(corr, n)
        if abs(corr) < MIN_CORR_ABS:
            continue
        if n >= 20 and pval > MIN_CORR_PVALUE:
            continue

        hit_pct, hit_n = lead_lag_hit_rate(focus_rets, node_rets, lag, corr)
        regime_break = correlation_regime_break(focus_rets, node_rets)

        c = df["Close"]
        m1 = (c.iloc[-1] / c.iloc[-2] - 1) * 100 if len(c) >= 2 else 0.0
        m5 = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0.0
        role = MACRO_NODES.get(sym) or sym
        if lag > 0:
            note = f"Leads {focus} by ~{lag}d (corr {corr:+.2f})"
        elif lag < 0:
            note = f"Lags {focus} by ~{-lag}d (corr {corr:+.2f})"
        else:
            note = f"Moves with {focus} (corr {corr:+.2f})"

        hit_note = ""
        if hit_pct is not None and hit_n >= 8:
            hit_note = f"; fwd hit {hit_pct:.0f}% (n={hit_n})"
        if regime_break:
            note += " [regime shift]"

        links.append(
            ChainLink(
                node=sym,
                layer=layer,
                direction=direction,
                role=role,
                corr_21d=round(corr, 3),
                lead_lag_days=lag,
                move_1d_pct=round(m1, 2),
                move_5d_pct=round(m5, 2),
                last_price=round(float(c.iloc[-1]), 2),
                note=note + hit_note,
                corr_pvalue=round(pval, 4),
                sample_n=n,
                lag_hit_rate=hit_pct,
                lag_hit_n=hit_n,
                corr_significant=corr_significant(corr, n),
                regime_break=regime_break,
            )
        )

    links.sort(key=lambda x: abs(x.corr_21d), reverse=True)

    events: List[ChainEvent] = []
    events.extend(_significant_moves(focus, focus_df, "micro", "focus"))
    for link in links[:12]:
        df = node_data.get(link.node)
        if df is not None:
            events.extend(
                _significant_moves(link.node, df, link.layer, link.direction)
            )
    events.sort(key=lambda e: e.date)

    narrative = _build_narrative(pick, links, events)
    return MomentumChain(
        focus=pick,
        links=links,
        events=events,
        narrative=narrative,
        scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _micro_catalysts(ticker: str) -> List[str]:
    """Earnings + trader attention snippets for the focus name."""
    notes: List[str] = []
    try:
        import earnings_drift
        sig = earnings_drift.analyze_earnings(ticker)
        if sig and sig.signal == "BUY":
            notes.append(
                f"Catalyst: earnings beat +{sig.surprise_pct:.0f}% ({sig.earnings_date})"
            )
        elif sig and sig.signal == "AVOID":
            notes.append(f"Catalyst: earnings miss {sig.surprise_pct:.0f}%")
    except Exception:
        pass
    try:
        import trader_attention
        score = trader_attention.trend_score(ticker)
        if score is not None:
            bias = "bullish" if score > 0.2 else "bearish" if score < -0.2 else "mixed"
            notes.append(f"Trader attention ({bias}, score {score:+.2f})")
    except Exception:
        pass
    return notes


def _build_narrative(
    pick: VolatilePick,
    links: List[ChainLink],
    events: List[ChainEvent],
) -> List[str]:
    lines = [
        f"{pick.ticker} ranks #{pick.rank} volatility ({pick.vol_annualized_pct:.0f}% ann., "
        f"5d {pick.return_5d_pct:+.1f}%, vol {pick.volume_ratio:.1f}x avg).",
    ]
    lines.extend(_micro_catalysts(pick.ticker))
    leaders = [l for l in links if l.lead_lag_days > 0 and l.direction == "upstream"]
    if leaders:
        top = leaders[0]
        lines.append(
            f"Macro/micro upstream leader: {top.node} ({top.role}) — {top.note}."
        )
    followers = [l for l in links if l.lead_lag_days < 0 and l.direction == "downstream"]
    if followers:
        top = followers[0]
        lines.append(
            f"Likely downstream reaction: {top.node} — {top.note}."
        )
    recent = [e for e in events if e.node == pick.ticker][-3:]
    if recent:
        seq = ", ".join(f"{e.date} {e.move_pct:+.1f}%" for e in recent)
        lines.append(f"Recent focus moves: {seq}.")
    elif events:
        last = events[-3:]
        seq = "; ".join(f"{e.date} {e.node} {e.move_pct:+.1f}%" for e in last)
        lines.append(f"Recent chain activity: {seq}.")
    return lines


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MomentumChainFinder:
    def __init__(self, top_n: int = DEFAULT_TOP_N):
        self.top_n = top_n

    def scan(self, universe: Optional[List[str]] = None) -> MomentumScanResult:
        tickers = universe or load_scan_universe()
        logger.info("Ranking volatility across %d tickers...", len(tickers))

        all_data = _bulk_download(tickers)
        top, focus_data = rank_by_volatility(tickers, self.top_n, prefetched=all_data)

        # Download macro + thematic nodes not in universe batch
        extra_syms: List[str] = list(MACRO_NODES.keys())
        for p in top:
            for sym, _, _ in _candidate_nodes(p.ticker):
                extra_syms.append(sym)
        extra_syms = [s for s in extra_syms if s not in all_data]
        if extra_syms:
            all_data.update(_bulk_download(extra_syms))

        chains: List[MomentumChain] = []
        for pick in top:
            df = focus_data.get(pick.ticker)
            if df is None:
                df = all_data.get(pick.ticker)
            if df is None or df.empty:
                continue
            logger.info("  Chain: #%d %s (vol %.0f%%)", pick.rank, pick.ticker, pick.vol_annualized_pct)
            chains.append(build_chain(pick, df, all_data))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return MomentumScanResult(
            scan_time=now,
            universe_size=len(tickers),
            top_volatile=top,
            chains=chains,
        )


def save_result(
    result: MomentumScanResult,
    path: Optional[str] = None,
    plays: Optional[list] = None,
) -> str:
    path = path or f"momentum_chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    def _serialize(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _serialize(v) for k, v in asdict(obj).items()}
        if isinstance(obj, list):
            return [_serialize(x) for x in obj]
        return obj

    payload = _serialize(result)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    try:
        import momentum_history
        momentum_history.append_scan(result, plays)
    except Exception as e:
        logger.debug("history append failed: %s", e)
    return path


def format_report(result: MomentumScanResult) -> str:
    lines = [
        "=" * 72,
        "  MOMENTUM CHAIN SCAN",
        f"  {result.scan_time} | universe {result.universe_size} → focus top {len(result.top_volatile)}",
        "=" * 72,
        "",
        "TOP VOLATILE (right now)",
        "-" * 40,
    ]
    for p in result.top_volatile:
        lines.append(
            f"  #{p.rank:2d} {p.ticker:6s}  score {p.composite_score:5.1f}  "
            f"vol {p.vol_annualized_pct:5.1f}%  exp×{p.vol_expansion:.2f}  "
            f"5d {p.return_5d_pct:+6.2f}%  1d {p.return_1d_pct:+5.2f}%  vol×{p.volume_ratio:.1f}"
        )

    for chain in result.chains:
        f = chain.focus
        lines.extend(["", "=" * 72, f"  {f.ticker}  (#{f.rank} volatile)", "=" * 72])
        for line in chain.narrative:
            lines.append(f"  • {line}")

        up = [l for l in chain.links if l.direction == "upstream"]
        down = [l for l in chain.links if l.direction == "downstream"]
        if up:
            lines.append("\n  UPSTREAM (watch first)")
            for l in up[:8]:
                lines.append(
                    f"    [{l.layer}] {l.node:8s}  corr {l.corr_21d:+.2f}  "
                    f"lag {l.lead_lag_days:+d}d  1d {l.move_1d_pct:+5.2f}%  — {l.note}"
                )
        if down:
            lines.append("\n  DOWNSTREAM (may follow)")
            for l in down[:6]:
                lines.append(
                    f"    [{l.layer}] {l.node:8s}  corr {l.corr_21d:+.2f}  "
                    f"lag {l.lead_lag_days:+d}d  1d {l.move_1d_pct:+5.2f}%"
                )

        if chain.events:
            lines.append("\n  EVENT CHAIN (moves ≥1.5%)")
            for e in chain.events[-15:]:
                arrow = "↑" if e.direction == "up" else "↓"
                lines.append(
                    f"    {e.date}  {e.node:8s}  {arrow} {abs(e.move_pct):.1f}%  "
                    f"({e.layer}/{e.relation})"
                )

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    finder = MomentumChainFinder(top_n=DEFAULT_TOP_N)
    result = finder.scan()
    print(format_report(result))
    out = save_result(result)
    print(f"\nSaved: {out}")
