#!/usr/bin/env python3
"""
Full analysis: do the path-less-travelled filters (SEC filing risk, Wikipedia momentum)
actually improve backtest results?

We run the winning strategy (earnings 40-100%, bull, 40d), get per-signal returns, then
filter by current SEC "clean" and/or Wikipedia trend. Compare metrics across variants.

Note: Uses *current* SEC/Wiki state as a proxy (we don't have historical 10-K/Wiki data
per signal date). So this answers: "Would filtering to tickers that are clean today and
have rising Wiki attention have improved our historical returns?"
"""

import json
import logging
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Same universe as run_winning_strategy (subset for faster run; use full for final)
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


def load_winning_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "backtest_cache", "winning_strategy.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def run_winning_backtest(universe: List[str]) -> Tuple[object, pd.DataFrame]:
    """Run winning strategy backtest; return (BacktestResult, returns_df)."""
    from backtest_engine import (
        BacktestConfig,
        fetch_and_cache_prices,
        load_earnings_history,
        run_backtest,
    )
    cfg = load_winning_config()
    ws = cfg.get("winning_strategy", {})
    hold_days = int(ws.get("hold_days", 40))
    min_surprise = float(ws.get("min_surprise_pct", 40))
    max_surprise = float(ws.get("max_surprise_pct", 100))
    bull = bool(ws.get("require_bull_regime", True))

    logger.info("Fetching price and earnings data for %d tickers ...", len(universe))
    data, spy = fetch_and_cache_prices(universe, days=756)
    earn = load_earnings_history(list(data.keys()))
    bc = BacktestConfig(
        name="earn_h40_surp40_100_bullTrue",
        hold_days=hold_days,
        min_surprise_pct=min_surprise,
        max_surprise_pct=max_surprise,
        require_bull_regime=bull,
        signal_type="earnings",
    )
    result, returns_df = run_backtest(data, spy, earn, bc)
    logger.info("Baseline: n=%d  median_alpha=%.2f%%  alpha_hit=%.1f%%  win_rate=%.1f%%",
                result.n_signals, result.median_alpha_pct, result.alpha_hit_rate_pct, result.win_rate_pct)
    return result, returns_df


def metrics_from_returns(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"n": 0, "median_alpha": 0, "mean_alpha": 0, "alpha_hit_pct": 0, "win_rate_pct": 0}
    n = len(df)
    median_alpha = float(df["alpha_pct"].median())
    mean_alpha = float(df["alpha_pct"].mean())
    alpha_hit = 100 * (df["alpha_pct"] > 0).sum() / n
    win_rate = 100 * (df["return_pct"] > 0).sum() / n
    return {
        "n": n,
        "median_alpha": round(median_alpha, 2),
        "mean_alpha": round(mean_alpha, 2),
        "alpha_hit_pct": round(alpha_hit, 1),
        "win_rate_pct": round(win_rate, 1),
    }


def build_sec_clean_set(tickers: List[str], config: dict) -> Set[str]:
    try:
        import sec_filing_risk as sec_risk
    except ImportError:
        return set()
    out = set()
    for t in tickers:
        clean, _, _ = sec_risk.is_clean(t, config)
        if clean:
            out.add(t.upper())
    return out


def build_wiki_scores(tickers: List[str], config: dict) -> Dict[str, float]:
    try:
        import wikipedia_views as wiki_views
    except ImportError:
        return {}
    out = {}
    for t in tickers:
        out[t.upper()] = wiki_views.trend_score(t, 14, config)
    return out


def main():
    import argparse
    p = argparse.ArgumentParser(description="Analyze SEC + Wikipedia filters on winning strategy backtest")
    p.add_argument("--skip-sec", action="store_true", help="Skip SEC API calls (only compare Wiki / baseline)")
    p.add_argument("--skip-wiki", action="store_true", help="Skip Wikipedia API calls (only compare SEC / baseline)")
    p.add_argument("--small", action="store_true", help="Use small universe (20 tickers) for quick run")
    args = p.parse_args()

    universe = DEFAULT_UNIVERSE[:20] if args.small else DEFAULT_UNIVERSE
    cfg = load_winning_config()

    result, returns_df = run_winning_backtest(universe)
    if returns_df is None or returns_df.empty:
        logger.error("No returns from backtest")
        sys.exit(1)

    unique_tickers = returns_df["ticker"].str.upper().unique().tolist()
    logger.info("Unique tickers in backtest signals: %d", len(unique_tickers))

    sec_clean: Set[str] = set()
    wiki_scores: Dict[str, float] = {}

    if not args.skip_sec:
        logger.info("Building SEC 'clean' set (current 10-K/10-Q risk check) ...")
        sec_clean = build_sec_clean_set(unique_tickers, cfg)
        logger.info("SEC clean tickers: %d / %d", len(sec_clean), len(unique_tickers))
    if not args.skip_wiki:
        logger.info("Building Wikipedia trend scores (current 14d) ...")
        wiki_scores = build_wiki_scores(unique_tickers, cfg)
        if wiki_scores:
            sorted_tickers = sorted(wiki_scores.keys(), key=lambda x: wiki_scores.get(x, 0), reverse=True)
            top50_count = max(1, len(sorted_tickers) // 2)
            wiki_top50_set = set(sorted_tickers[:top50_count])
            logger.info("Wikipedia: top-50%% tickers = %d", len(wiki_top50_set))
        else:
            wiki_top50_set = set()
    else:
        wiki_top50_set = set()

    # Variants
    variants = []
    # Baseline
    variants.append(("Baseline (no filter)", returns_df))

    if sec_clean:
        sec_df = returns_df[returns_df["ticker"].str.upper().isin(sec_clean)]
        variants.append(("SEC clean only", sec_df))

    if wiki_scores:
        wiki_positive = returns_df[returns_df["ticker"].str.upper().apply(lambda t: wiki_scores.get(t.upper(), 0) > 0)]
        variants.append(("Wiki trend > 0", wiki_positive))
        if wiki_top50_set:
            wiki_top50_df = returns_df[returns_df["ticker"].str.upper().isin(wiki_top50_set)]
            variants.append(("Wiki top 50% by trend", wiki_top50_df))

    if sec_clean and wiki_scores:
        sec_and_wiki = returns_df[
            returns_df["ticker"].str.upper().isin(sec_clean) &
            (returns_df["ticker"].str.upper().apply(lambda t: wiki_scores.get(t.upper(), 0) > 0))
        ]
        variants.append(("SEC clean + Wiki > 0", sec_and_wiki))

    # Report
    logger.info("")
    logger.info("=" * 70)
    logger.info("PATH-LESS-TRAVELLED FILTER ANALYSIS")
    logger.info("=" * 70)
    rows = []
    for name, df in variants:
        m = metrics_from_returns(df)
        rows.append({
            "variant": name,
            "n": m["n"],
            "median_alpha_%": m["median_alpha"],
            "mean_alpha_%": m["mean_alpha"],
            "alpha_hit_%": m["alpha_hit_pct"],
            "win_rate_%": m["win_rate_pct"],
        })
    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    logger.info("")

    # Recommendation
    best = max(rows, key=lambda r: (r["n"] >= 15, r["median_alpha_%"], r["alpha_hit_%"]))
    logger.info("Best variant (median_alpha, then alpha_hit, min n>=15): %s", best["variant"])
    logger.info("  n=%d  median_alpha=%.2f%%  alpha_hit=%.1f%%  win_rate=%.1f%%",
                best["n"], best["median_alpha_%"], best["alpha_hit_%"], best["win_rate_%"])

    baseline = rows[0]
    if best["variant"] != baseline["variant"] and best["n"] >= 15:
        logger.info("")
        logger.info("Recommendation: USE FILTERS — %s improves over baseline.", best["variant"])
    elif sec_clean:
        sec_metrics = metrics_from_returns(returns_df[returns_df["ticker"].str.upper().isin(sec_clean)])
        if sec_metrics["n"] >= 15 and sec_metrics["median_alpha"] > baseline["median_alpha_%"]:
            logger.info("")
            logger.info("Recommendation: SEC filter improves median alpha; consider keeping it on.")
        else:
            logger.info("")
            logger.info("Recommendation: Baseline is best or filters reduce n too much. Run without --sec-filter and without --wiki-rank for live.")
    elif wiki_scores and best["variant"].startswith("Wiki") and best["median_alpha_%"] > baseline["median_alpha_%"]:
        logger.info("")
        logger.info("Recommendation: Wikipedia filter improves results; consider --wiki-rank in live run.")
    else:
        logger.info("")
        logger.info("Recommendation: Baseline is best or filters reduce n too much. Run without --sec-filter and without --wiki-rank for live.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
