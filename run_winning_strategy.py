#!/usr/bin/env python3
"""
Live runner for the backtested winning strategy.

Strategy: earnings_buy_entry_delay_1 (backtested profitable)
  - Buy on earnings beat (surprise ≥10%), enter next trading day, hold 40 days
  - Only when SPY is above 200d MA (bull regime)

Path less travelled (free filters):
  - SEC filing risk: off by default; use --sec-filter to drop tickers with risk phrases in 10-K/10-Q.
  - Wikipedia momentum: use --wiki-rank to rank by rising pageviews.

Usage:
  ./venv/bin/python run_winning_strategy.py              # print current signals
  ./venv/bin/python run_winning_strategy.py --json      # machine-readable
  ./venv/bin/python run_winning_strategy.py --sec-filter --wiki-rank
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

# Optional path-less-travelled filters (free SEC + Wikipedia)
try:
    import sec_filing_risk as _sec_risk
    _SEC_AVAILABLE = True
except ImportError:
    _SEC_AVAILABLE = False
try:
    import wikipedia_views as _wiki_views
    _WIKI_AVAILABLE = True
except ImportError:
    _WIKI_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Default universe (same as backtest)
DEFAULT_UNIVERSE = [
    "CRWD", "DDOG", "NET", "ZS", "MDB", "HUBS", "DOCN", "S", "GTLB", "IOT",
    "BRZE", "DT", "CFLT", "PD", "SOFI", "HOOD", "AFRM", "UPST", "LMND", "LC", "NU",
    "TGTX", "KPTI", "PTCT", "RARE", "BMRN", "ALNY", "SRPT", "NBIX",
    "EXAS", "HALO", "PCVX", "LEGN", "BEAM", "CRSP", "NTLA",
    "CELH", "CAVA", "ELF", "ONON", "CROX", "SHAK", "BROS", "DKS",
    "AXON", "BLDR", "GNRC", "CLF", "AA", "MP", "FANG", "MTDR",
    "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI",
    "FUBO", "PLUG", "CLOV", "LCID", "RIVN", "ENPH", "FSLR", "RUN",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META",
    "JPM", "V", "UNH", "COIN", "RBLX", "NKTR", "MRNA", "BNTX", "PYPL",
    "STRL", "ATKR", "UFPI", "AR", "RRC", "EQT", "IRM", "EQIX",
    "JOBY", "ACHR", "RGTI", "QUBT", "DNA", "EDIT", "BFLY", "NNOX",
    "OUST", "INVZ", "STEM", "ARRY",
]
DEFAULT_UNIVERSE = list(dict.fromkeys(u.upper() for u in DEFAULT_UNIVERSE))

HOLD_DAYS = 40
# Backtested profitable (backtest_profitable.py): earnings BUY, min_surprise 10%, entry_delay=1
MIN_SURPRISE_PCT = 10
MAX_SURPRISE_PCT = 100
ENTRY_DELAY_DAYS = 1  # only signal when earnings was at least 1 trading day ago (enter "next day")
LOOKBACK_DAYS = 15  # consider earnings in last 15 days

# Aggressive mode: fewer signals, higher conviction (aim toward 80% hit rate)
AGGRESSIVE_HOLD_DAYS = 20
AGGRESSIVE_TOP_PCT = 0.25  # keep only top 25% by surprise


def load_config() -> dict:
    # Prefer backtested profitable params when present
    profitable = os.path.join(os.path.dirname(__file__), "backtest_cache", "profitable_params.json")
    if os.path.exists(profitable):
        with open(profitable) as f:
            data = json.load(f)
            return {"winning_strategy": data}
    path = os.path.join(os.path.dirname(__file__), "backtest_cache", "winning_strategy.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def is_bull_regime() -> bool:
    """True if SPY is above its 200-day SMA."""
    try:
        spy = yf.Ticker("SPY")
        df = spy.history(period="250d")
        if df is None or len(df) < 200:
            return True  # assume bull if we can't get data
        df.index = df.index.tz_localize(None) if hasattr(df.index, "tz") and df.index.tz else df.index
        close = df["Close"].iloc[-1]
        sma200 = df["Close"].rolling(200).mean().iloc[-1]
        return float(close) >= float(sma200)
    except Exception:
        return True


def _float(v) -> Optional[float]:
    if v is None or (hasattr(v, "__float__") and str(v) == "nan"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_earnings_surprise(ticker: str) -> Optional[dict]:
    """Get most recent earnings surprise for ticker. Returns {date, surprise_pct, eps_actual, eps_estimate} or None."""
    try:
        tk = yf.Ticker(ticker)
        ed = tk.earnings_dates
        if ed is None or ed.empty:
            return None
    except Exception:
        return None

    now = pd.Timestamp.now()
    if ed.index.tz is not None and now.tzinfo is None:
        now = now.tz_localize(ed.index.tz)
    cutoff = now - pd.Timedelta(days=LOOKBACK_DAYS)
    past = ed[(ed.index <= now) & (ed.index >= cutoff)].copy()
    if past.empty:
        return None

    past = past.sort_index(ascending=False)
    row = past.iloc[0]
    earn_date = past.index[0]
    # Entry delay: only use if earnings was at least ENTRY_DELAY_DAYS ago (we "enter" next day)
    if (now - earn_date).days < ENTRY_DELAY_DAYS:
        return None
    eps_actual = _float(row.get("Reported EPS"))
    eps_estimate = _float(row.get("EPS Estimate"))
    if eps_actual is None or eps_estimate is None:
        return None
    if abs(eps_estimate) < 0.001:
        surprise_pct = 100.0 if eps_actual > 0 else 0.0
    else:
        surprise_pct = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100.0

    return {
        "date": earn_date.strftime("%Y-%m-%d"),
        "surprise_pct": round(surprise_pct, 1),
        "eps_actual": eps_actual,
        "eps_estimate": eps_estimate,
    }


def scan(
    universe: List[str] = None,
    aggressive: bool = False,
    use_sec_filter: bool = True,
    use_wiki_rank: bool = False,
    config: Optional[Dict] = None,
) -> List[dict]:
    """
    Scan universe for current signals.
    If aggressive=True: hold 20d, keep only top 25% of signals by surprise (fewer, higher conviction).
    If use_sec_filter=True (and sec_filing_risk available): drop tickers whose latest 10-K/10-Q has risk phrases.
    If use_wiki_rank=True (and wikipedia_views available): sort remaining by Wikipedia pageview trend (rising first).
    Returns list of {ticker, earnings_date, surprise_pct, eps_actual, eps_estimate, price, hold_days, ...}.
    """
    universe = universe or DEFAULT_UNIVERSE
    bull = is_bull_regime()
    if not bull:
        logger.info("SPY is below 200d MA — not in bull regime. No new signals.")
        return []

    hold = AGGRESSIVE_HOLD_DAYS if aggressive else HOLD_DAYS
    signals = []
    for ticker in universe:
        try:
            rec = get_earnings_surprise(ticker)
            if rec is None:
                continue
            surp = rec["surprise_pct"]
            if surp < MIN_SURPRISE_PCT or surp > MAX_SURPRISE_PCT:
                continue
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist is None or hist.empty:
                continue
            price = float(hist["Close"].iloc[-1])
            signals.append({
                "ticker": ticker,
                "earnings_date": rec["date"],
                "surprise_pct": surp,
                "eps_actual": rec["eps_actual"],
                "eps_estimate": rec["eps_estimate"],
                "price": round(price, 2),
                "hold_days": hold,
            })
        except Exception as e:
            logger.debug("%s: %s", ticker, e)

    # SEC filing risk filter: only keep "clean" tickers (no going-concern / material-weakness language)
    if use_sec_filter and _SEC_AVAILABLE and signals:
        cfg = config or {}
        filtered = []
        for s in signals:
            clean, form, risk_count = _sec_risk.is_clean(s["ticker"], cfg)
            if clean:
                filtered.append(s)
            else:
                logger.debug("SEC filter out %s (form=%s risk_phrases=%d)", s["ticker"], form, risk_count)
        dropped = len(signals) - len(filtered)
        if dropped:
            logger.info("SEC filing filter: dropped %d signal(s) with risk language in latest 10-K/10-Q.", dropped)
        signals = filtered

    if aggressive and len(signals) > 1:
        # Keep only top 25% by surprise
        signals.sort(key=lambda x: x["surprise_pct"], reverse=True)
        keep = max(1, int(len(signals) * AGGRESSIVE_TOP_PCT))
        signals = signals[:keep]

    # Optional: rank by Wikipedia pageview momentum (rising attention first)
    if use_wiki_rank and _WIKI_AVAILABLE and len(signals) > 1:
        cfg = config or {}
        def wiki_key(s):
            return _wiki_views.trend_score(s["ticker"], 14, cfg)
        signals.sort(key=wiki_key, reverse=True)
        logger.info("Ranked signals by Wikipedia pageview momentum (rising first).")

    return signals


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--universe", nargs="+", help="Override universe")
    p.add_argument("--mode", choices=["default", "aggressive"], default="default",
                   help="aggressive = hold 20d, top 25%% by surprise (fewer, higher-conviction)")
    p.add_argument("--sec-filter", action="store_true",
                   help="Enable SEC filing risk filter (drop tickers with risk phrases in 10-K/10-Q)")
    p.add_argument("--wiki-rank", action="store_true",
                   help="Rank signals by Wikipedia pageview momentum (rising attention first)")
    args = p.parse_args()

    aggressive = args.mode == "aggressive"
    cfg = load_config()
    use_sec = args.sec_filter   # default OFF per analyze_path_less_travelled.py results
    use_wiki = args.wiki_rank
    if cfg:
        s = cfg.get("winning_strategy", {})
        logger.info("Strategy: %s (hold %dd, surprise %s-%s%%, bull only)%s",
                    s.get("strategy", s.get("name", "earn_h40_surp40_100_bullTrue")),
                    AGGRESSIVE_HOLD_DAYS if aggressive else s.get("hold_days", HOLD_DAYS),
                    s.get("min_surprise_pct", MIN_SURPRISE_PCT),
                    s.get("max_surprise_pct", MAX_SURPRISE_PCT),
                    " [AGGRESSIVE: top 25%% by surprise]" if aggressive else "")
    if use_sec and _SEC_AVAILABLE:
        logger.info("SEC filing risk filter: ON (drop tickers with risk phrases in latest 10-K/10-Q)")
    elif use_sec and not _SEC_AVAILABLE:
        logger.info("SEC filing risk filter: requested but sec_filing_risk not available")
    if use_wiki and _WIKI_AVAILABLE:
        logger.info("Wikipedia momentum ranking: ON")

    universe = args.universe or DEFAULT_UNIVERSE
    results = scan(universe, aggressive=aggressive, use_sec_filter=use_sec, use_wiki_rank=use_wiki, config=cfg)

    if args.json:
        print(json.dumps({"bull_regime": is_bull_regime(), "aggressive": aggressive, "signals": results}, indent=2))
        return

    hold = AGGRESSIVE_HOLD_DAYS if aggressive else HOLD_DAYS
    logger.info("Bull regime: %s", is_bull_regime())
    logger.info("Current signals (earnings beat ≥10%%, enter next day, hold %d days)%s: %d",
                hold, " [aggressive]" if aggressive else "", len(results))
    for r in results:
        logger.info("  %s  earnings %s  surprise %+.1f%%  price $%s  (hold %d days)",
                    r["ticker"], r["earnings_date"], r["surprise_pct"], r["price"], r["hold_days"])


if __name__ == "__main__":
    main()
