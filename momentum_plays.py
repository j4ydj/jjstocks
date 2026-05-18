#!/usr/bin/env python3
"""
Turn momentum chain scans into actionable trade plays.

Play types:
  chain_trend     — focus direction aligned with 5d momentum + upstream
  pullback        — buy/sell dip/rally in established chain trend
  catch_up        — focus lags a leading upstream name (same chain)
  downstream      — downstream name hasn't followed focus spike yet
  macro_hedge     — reduce risk when macro upstream flips against position
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from momentum_chain import (
    MomentumChain,
    MomentumScanResult,
    MomentumChainFinder,
    ChainLink,
    _bulk_download,
)

logger = logging.getLogger(__name__)

HOLD_DAYS_DEFAULT = 10  # shorter hold — vol names move fast


@dataclass
class TradePlay:
    play_type: str
    ticker: str
    direction: str
    entry_price: float
    stop_loss: float
    target_price: float
    risk_pct: float
    reward_pct: float
    risk_reward: float
    position_pct: float
    hold_days: int
    exit_date: str
    conviction: int
    trigger: str
    invalidation: str
    thesis: List[str]
    watchlist: List[str]
    related_ticker: Optional[str] = None
    basket_tickers: Optional[List[str]] = None
    score: int = 0
    trigger_price: Optional[float] = None


def _levels(
    ticker: str,
    df: pd.DataFrame,
    direction: str,
    conviction: int,
) -> Optional[Tuple[float, float, float, float, float, float]]:
    from trade_levels import calculate_levels
    t = calculate_levels(
        ticker, direction, df, conviction=max(3, min(5, conviction)), hold_days=HOLD_DAYS_DEFAULT
    )
    if t is None:
        return None
    return (
        t.entry_price, t.stop_loss, t.target_price,
        t.risk_pct, t.reward_pct, t.position_pct,
    )


def _risk_regime(links: List[ChainLink]) -> str:
    if _vix_stress(links):
        return "risk_off"
    bias = _upstream_bias(links)
    if bias > 0:
        return "risk_on"
    if bias < 0:
        return "risk_off"
    return "neutral"


def _apply_regime(plays: List[TradePlay], regime: str) -> List[TradePlay]:
    out: List[TradePlay] = []
    for pl in plays:
        if pl.direction == "BUY" and regime == "risk_off":
            continue
        if pl.direction == "SHORT" and regime == "risk_on":
            continue
        out.append(pl)
    return out


def _macro_upstream(links: List[ChainLink]) -> List[ChainLink]:
    return [l for l in links if l.direction == "upstream" and l.layer == "macro"]


def _micro_upstream(links: List[ChainLink]) -> List[ChainLink]:
    return [l for l in links if l.direction == "upstream" and l.layer == "micro"]


def _downstream(links: List[ChainLink]) -> List[ChainLink]:
    return [l for l in links if l.direction == "downstream"]


def _upstream_bias(links: List[ChainLink]) -> float:
    """+1 bullish upstream day, -1 bearish, 0 mixed."""
    macro = _macro_upstream(links)[:5]
    if not macro:
        return 0.0
    ups = sum(1 for l in macro if l.move_1d_pct > 0.3)
    downs = sum(1 for l in macro if l.move_1d_pct < -0.3)
    if ups >= 3 and downs <= 1:
        return 1.0
    if downs >= 3 and ups <= 1:
        return -1.0
    return 0.0


def _vix_stress(links: List[ChainLink]) -> bool:
    for l in links:
        if l.node == "^VIX" and l.move_1d_pct > 4:
            return True
    return False


def _chain_score(chain: MomentumChain) -> Tuple[float, List[str]]:
    """Signed score: positive = bullish focus, negative = bearish."""
    p = chain.focus
    reasons: List[str] = []
    score = 0.0

    if p.return_5d_pct > 5:
        score += 35
        reasons.append(f"5d momentum +{p.return_5d_pct:.1f}%")
    elif p.return_5d_pct < -5:
        score -= 35
        reasons.append(f"5d momentum {p.return_5d_pct:.1f}%")

    if p.return_1d_pct > 2:
        score += 20
        reasons.append(f"1d thrust +{p.return_1d_pct:.1f}%")
    elif p.return_1d_pct < -2:
        score -= 20
        reasons.append(f"1d flush {p.return_1d_pct:.1f}%")

    bias = _upstream_bias(chain.links)
    if bias > 0:
        score += 25
        reasons.append("macro upstream supportive (1d)")
    elif bias < 0:
        score -= 25
        reasons.append("macro upstream weak (1d)")

    peers = _micro_upstream(chain.links)[:3]
    if peers:
        peer_avg = sum(l.move_1d_pct for l in peers) / len(peers)
        if peer_avg > 1 and p.return_5d_pct > 0:
            score += 15
            reasons.append(f"peer chain firm (avg 1d {peer_avg:+.1f}%)")
        elif peer_avg < -1 and p.return_5d_pct < 0:
            score -= 15
            reasons.append(f"peer chain soft (avg 1d {peer_avg:+.1f}%)")

    if _vix_stress(chain.links):
        score -= 20
        reasons.append("VIX spike — risk-off")

    return score, reasons


def _watchlist(chain: MomentumChain) -> List[str]:
    nodes = []
    for l in chain.links:
        if l.direction == "upstream" and abs(l.corr_21d) >= 0.4:
            nodes.append(l.node)
    return list(dict.fromkeys(nodes))[:6]


def _make_play(
    play_type: str,
    ticker: str,
    direction: str,
    df: pd.DataFrame,
    conviction: int,
    trigger: str,
    invalidation: str,
    thesis: List[str],
    watchlist: List[str],
    related: Optional[str] = None,
) -> Optional[TradePlay]:
    lv = _levels(ticker, df, direction, conviction)
    if lv is None:
        return None
    entry, stop, target, risk_pct, reward_pct, pos_pct = lv
    if entry <= 0 or entry > 600:  # skip bad yfinance prints (e.g. MU/SNDK anomalies)
        logger.debug("skip play %s: suspicious entry %.2f", ticker, entry)
        return None
    rr = reward_pct / risk_pct if risk_pct > 0 else 0
    exit_d = (datetime.now() + timedelta(days=HOLD_DAYS_DEFAULT)).strftime("%Y-%m-%d")
    trigger_price = None
    if len(df) >= 2:
        if direction == "BUY":
            trigger_price = round(float(df["Low"].iloc[-2]), 2)
        else:
            trigger_price = round(float(df["High"].iloc[-2]), 2)
    return TradePlay(
        play_type=play_type,
        ticker=ticker,
        direction=direction,
        entry_price=entry,
        stop_loss=stop,
        target_price=target,
        risk_pct=risk_pct,
        reward_pct=reward_pct,
        risk_reward=round(rr, 1),
        position_pct=pos_pct,
        hold_days=HOLD_DAYS_DEFAULT,
        exit_date=exit_d,
        conviction=conviction,
        trigger=trigger,
        invalidation=invalidation,
        thesis=thesis,
        watchlist=watchlist,
        related_ticker=related,
        trigger_price=trigger_price,
    )


def plays_from_chain(
    chain: MomentumChain,
    df: pd.DataFrame,
    node_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[TradePlay]:
    """Generate 0–3 plays for one focus chain."""
    plays: List[TradePlay] = []
    p = chain.focus
    score, score_reasons = _chain_score(chain)
    watch = _watchlist(chain)
    leaders = [l for l in chain.links if l.lead_lag_days > 0 and l.direction == "upstream"]
    downstream = _downstream(chain.links)
    regime = _risk_regime(chain.links)

    # --- 1) Chain trend: directional when score is strong and upstream agrees ---
    if score >= 45:
        thesis = score_reasons + [f"Trade with chain momentum on #{p.rank} vol name."]
        inv = f"Stop ${'below' if 'BUY' else 'above'} invalidation; macro upstream flips red 2 days."
        pl = _make_play(
            "chain_trend",
            p.ticker,
            "BUY",
            df,
            conviction=4 if score >= 60 else 3,
            trigger=f"Enter {p.ticker} while upstream holds; watch {', '.join(watch[:3])}",
            invalidation=inv,
            thesis=thesis,
            watchlist=watch,
        )
        if pl:
            plays.append(pl)
    elif score <= -45:
        thesis = score_reasons + ["Short chain breakdown on volatile leader."]
        pl = _make_play(
            "chain_trend",
            p.ticker,
            "SHORT",
            df,
            conviction=4 if score <= -60 else 3,
            trigger=f"Short {p.ticker} if {watch[0] if watch else 'SPY'} weak at open",
            invalidation="Cover if macro upstream reverses +2% day",
            thesis=thesis,
            watchlist=watch,
        )
        if pl:
            plays.append(pl)

    # --- 2) Pullback in trend: 5d up, 1d down, upstream not broken ---
    if p.return_5d_pct > 6 and p.return_1d_pct < -2 and _upstream_bias(chain.links) >= 0:
        thesis = [
            f"5d trend +{p.return_5d_pct:.1f}% intact",
            f"1d pullback {p.return_1d_pct:.1f}% into support",
            "Macro upstream still green on 1d",
        ]
        pl = _make_play(
            "pullback",
            p.ticker,
            "BUY",
            df,
            conviction=3,
            trigger=f"Buy dip if {watch[0] if watch else 'QQQ'} flat/up; entry near prior day low",
            invalidation="5d trend breaks; stop hit",
            thesis=thesis,
            watchlist=watch,
        )
        if pl and not any(x.play_type == "pullback" for x in plays):
            plays.append(pl)

    # --- 3) Catch-up: positive-corr upstream leader led, focus lagging ---
    if leaders:
        eligible = [
            l for l in leaders
            if l.corr_21d > 0.35 and l.node != "^VIX" and l.move_5d_pct > 4
        ]
        if not eligible:
            eligible = []
        lead = max(eligible, key=lambda x: x.corr_21d) if eligible else None
        if lead and p.return_5d_pct < lead.move_5d_pct - 4:
            gap = lead.move_5d_pct - p.return_5d_pct
            thesis = [
                f"{lead.node} leads {p.ticker} by ~{lead.lead_lag_days}d (corr {lead.corr_21d:+.2f})",
                f"Leader 5d +{lead.move_5d_pct:.1f}% vs focus {p.return_5d_pct:+.1f}% ({gap:.1f}% gap)",
                "Catch-up if leader holds strength",
            ]
            pl = _make_play(
                "catch_up",
                p.ticker,
                "BUY",
                df,
                conviction=3,
                trigger=f"{lead.node} stays green → enter {p.ticker}",
                invalidation=f"{lead.node} loses 5d gains or focus breaks stop",
                thesis=thesis,
                watchlist=[lead.node] + watch[:3],
                related=lead.node,
            )
            if pl and not any(x.play_type == "catch_up" for x in plays):
                plays.append(pl)

    # --- 4) Downstream follow: focus ripped, downstream flat ---
    if p.return_1d_pct > 3 and downstream:
        lag = downstream[0]
        if abs(lag.move_1d_pct) < 1.5 and lag.corr_21d > 0.35:
            thesis = [
                f"{p.ticker} +{p.return_1d_pct:.1f}% 1d",
                f"{lag.node} not yet moved ({lag.move_1d_pct:+.1f}% 1d)",
                f"Corr {lag.corr_21d:+.2f} — downstream catch-up",
            ]
            ds_df = (node_data or {}).get(lag.node) or df
            pl = _make_play(
                "downstream",
                lag.node,
                "BUY",
                ds_df,
                conviction=3,
                trigger=f"After {p.ticker} holds gains, enter {lag.node}",
                invalidation=f"{p.ticker} reverses >3%; {lag.node} stop",
                thesis=thesis,
                watchlist=[p.ticker, lag.node],
                related=p.ticker,
            )
            if pl and not any(x.play_type == "downstream" and x.ticker == lag.node for x in plays):
                plays.append(pl)

    # --- 5) Thematic basket: tight peer cluster moving together ---
    peers = [l for l in _micro_upstream(chain.links) if l.corr_21d >= 0.7]
    if len(peers) >= 2 and p.return_5d_pct > 4 and regime != "risk_off":
        basket = list(dict.fromkeys([p.ticker] + [x.node for x in peers[:3]]))[:4]
        thesis = [
            f"Peer cluster corr ≥0.7: {', '.join(basket)}",
            f"Focus 5d {p.return_5d_pct:+.1f}% — trade as a theme, split risk",
        ]
        pl = _make_play(
            "thematic_basket",
            p.ticker,
            "BUY",
            df,
            conviction=3,
            trigger=f"Enter basket if {peers[0].node} and QQQ firm; equal weight",
            invalidation="Any peer breaks stop; macro risk-off",
            thesis=thesis,
            watchlist=watch,
        )
        if pl:
            pl.basket_tickers = basket
            if not any(x.play_type == "thematic_basket" for x in plays):
                plays.append(pl)

    # --- 6) Relative spread: focus extended vs top peer on 5d ---
    peers = _micro_upstream(chain.links)
    if peers and regime != "risk_off":
        peer = peers[0]
        spread = p.return_5d_pct - peer.move_5d_pct
        if spread > 8 and peer.corr_21d > 0.5:
            thesis = [
                f"{p.ticker} extended vs {peer.node}: 5d gap {spread:+.1f}%",
                f"Corr {peer.corr_21d:+.2f} — mean-reversion / pair fade",
            ]
            pl = _make_play(
                "relative_spread",
                p.ticker,
                "SHORT",
                df,
                conviction=3,
                trigger=f"Short {p.ticker} if {peer.node} stalls; long {peer.node} optional",
                invalidation=f"{peer.node} breaks out +3% 1d",
                thesis=thesis,
                watchlist=[peer.node, p.ticker],
                related=peer.node,
            )
            if pl and not any(x.play_type == "relative_spread" for x in plays):
                plays.append(pl)
        elif spread < -8 and peer.corr_21d > 0.5:
            thesis = [
                f"{p.ticker} lags {peer.node} by {abs(spread):.1f}% (5d)",
                "Long focus vs peer convergence",
            ]
            pl = _make_play(
                "relative_spread",
                p.ticker,
                "BUY",
                df,
                conviction=3,
                trigger=f"Long {p.ticker} if {peer.node} holds 5d gains",
                invalidation=f"{peer.node} rolls over >3% 1d",
                thesis=thesis,
                watchlist=[peer.node, p.ticker],
                related=peer.node,
            )
            if pl and not any(
                x.play_type in ("relative_spread", "catch_up") for x in plays
            ):
                plays.append(pl)

    return _apply_regime(plays, regime)


def chain_break_alerts(chain: MomentumChain) -> List[str]:
    """Warnings when macro upstream conflicts with focus direction."""
    alerts: List[str] = []
    p = chain.focus
    bias = _upstream_bias(chain.links)
    if p.return_5d_pct > 5 and bias < 0:
        alerts.append(f"{p.ticker}: 5d uptrend but macro upstream weak — longs at risk")
    if p.return_5d_pct < -5 and bias > 0:
        alerts.append(f"{p.ticker}: 5d downtrend but macro firm — shorts at risk")
    if _vix_stress(chain.links) and p.return_5d_pct > 0:
        alerts.append(f"{p.ticker}: VIX spike vs positive 5d — tighten stops on longs")
    return alerts


def build_plays(
    result: MomentumScanResult,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
    min_conviction: int = 3,
    max_plays: int = 8,
) -> List[TradePlay]:
    """Build plays for all chains; fetch prices for focus + downstream tickers."""
    tickers = [c.focus.ticker for c in result.chains]
    for c in result.chains:
        for l in _downstream(c.links)[:2]:
            tickers.append(l.node)
        for l in _micro_upstream(c.links)[:2]:
            tickers.append(l.node)
    tickers = list(dict.fromkeys(tickers))

    data = price_data or _bulk_download(tickers)
    all_plays: List[TradePlay] = []
    regimes: Dict[str, str] = {}

    for chain in result.chains:
        df = data.get(chain.focus.ticker)
        if df is None or df.empty:
            continue
        regimes[chain.focus.ticker] = _risk_regime(chain.links)
        chain_plays = plays_from_chain(chain, df, node_data=data)
        for pl in chain_plays:
            if pl.conviction >= min_conviction:
                all_plays.append(pl)

    from play_scoring import rank_plays
    ranked = rank_plays(all_plays, chains=result.chains, regimes=regimes, top_n=max_plays)
    return ranked


def collect_chain_alerts(result: MomentumScanResult) -> List[str]:
    out: List[str] = []
    for chain in result.chains:
        out.extend(chain_break_alerts(chain))
    return out


def scan_with_plays(
    top_n: int = 10,
    min_conviction: int = 3,
    max_plays: int = 8,
) -> Tuple[MomentumScanResult, List[TradePlay]]:
    finder = MomentumChainFinder(top_n=top_n)
    result = finder.scan()
    plays = build_plays(result, min_conviction=min_conviction, max_plays=max_plays)
    return result, plays


def scan_and_save(
    top_n: int = 10,
    min_conviction: int = 3,
    max_plays: int = 8,
) -> Tuple[MomentumScanResult, List[TradePlay], str]:
    result, plays = scan_with_plays(
        top_n=top_n, min_conviction=min_conviction, max_plays=max_plays
    )
    from momentum_chain import save_result
    path = save_result(result, plays=plays)
    return result, plays, path


def format_plays(plays: List[TradePlay]) -> str:
    if not plays:
        return "\n  No chain plays met conviction threshold.\n"
    lines = [
        "",
        "=" * 72,
        f"  TRADE PLAYS ({len(plays)})",
        "=" * 72,
    ]
    for i, pl in enumerate(plays, 1):
        d = "BUY" if pl.direction == "BUY" else "SHORT"
        basket = f"  basket: {', '.join(pl.basket_tickers)}" if pl.basket_tickers else ""
        lines.extend([
            "",
            f"  [{i}] {pl.play_type.upper()} — {d} {pl.ticker}"
            + (f" (vs {pl.related_ticker})" if pl.related_ticker else "")
            + basket,
            f"      Entry ${pl.entry_price}  Stop ${pl.stop_loss} ({pl.risk_pct}%)  "
            f"Target ${pl.target_price} (+{pl.reward_pct}%)  R:R {pl.risk_reward}",
            f"      Size {pl.position_pct}% portfolio  Hold ~{pl.hold_days}d until {pl.exit_date}",
            f"      Score {getattr(pl, 'score', 0)}/100  Conviction {pl.conviction}/5",
            f"      Trigger: {pl.trigger}",
            f"      Invalidation: {pl.invalidation}",
        ])
        if pl.trigger_price:
            lines.append(f"      Level: ${pl.trigger_price}")
        lines.extend([
            f"      Watch: {', '.join(pl.watchlist)}",
            "      Thesis:",
        ])
        for t in pl.thesis:
            lines.append(f"        - {t}")
    lines.append("\n" + "=" * 72)
    return "\n".join(lines)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result, plays = scan_with_plays()
    from momentum_chain import format_report
    print(format_report(result))
    print(format_plays(plays))
