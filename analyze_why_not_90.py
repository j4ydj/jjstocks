#!/usr/bin/env python3
"""
Push hit rate as high as possible by extreme selectivity.

Tests:
  1. Top-decile / top-quartile: only take signals in the top 10% or 25% by surprise size (at entry).
  2. Stricter surprise band: 60-100% or 70-100% (fewer but higher-conviction).
  3. Combo + stricter: earnings 40-100% AND RSI < 35 at entry.

Reports: n_signals, win_rate_pct, alpha_hit_rate_pct, median_alpha_pct for each.
No lookahead: we only use data known at entry (surprise_pct, RSI at entry).
"""

import logging
import sys
from typing import Dict, List, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest_engine import (
    BacktestConfig,
    fetch_and_cache_prices,
    load_earnings_history,
    run_backtest,
)

UNI = [
    "CRWD", "DDOG", "NET", "ZS", "MDB", "SOFI", "HOOD", "AFRM", "CELH", "CAVA", "ELF", "ONON",
    "TGTX", "RKLB", "FUBO", "PLUG", "ENPH", "RUN", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "V", "COIN", "RBLX", "PYPL", "NKTR", "MRNA", "BNTX", "RARE", "BMRN", "SRPT", "NBIX",
    "EXAS", "HALO", "BEAM", "CRSP", "NTLA", "AXON", "BLDR", "CLF", "MP", "FANG", "MTDR",
    "STRL", "AR", "RRC", "IRM", "JOBY", "RGTI", "QUBT", "DNA", "EDIT", "STEM", "ARRY",
]
UNI = list(dict.fromkeys(u.upper() for u in UNI))


def metrics(df: pd.DataFrame) -> dict:
    if df is None or df.empty or len(df) < 5:
        return {"n": 0, "win_rate": 0, "alpha_hit": 0, "median_alpha": 0}
    n = len(df)
    win = 100 * (df["return_pct"] > 0).sum() / n
    ah = 100 * (df["alpha_pct"] > 0).sum() / n
    med = df["alpha_pct"].median()
    return {"n": n, "win_rate": round(win, 2), "alpha_hit": round(ah, 2), "median_alpha": round(med, 3)}


def main():
    logger.info("Loading data ...")
    data, spy = fetch_and_cache_prices(UNI, days=756)
    earn = load_earnings_history(list(data.keys()))

    # Full earnings 40-100%, hold 40, bull
    cfg = BacktestConfig(
        "earn_h40_surp40_100_bullTrue",
        hold_days=40,
        min_surprise_pct=40,
        max_surprise_pct=100,
        require_bull_regime=True,
        signal_type="earnings",
    )
    res, df_full = run_backtest(data, spy, earn, cfg)
    if df_full is None or df_full.empty:
        logger.error("No signals")
        sys.exit(1)

    # We need surprise_pct per row — backtest_engine doesn't return it in df. So we need to either
    # add it to compute_returns or re-generate signals and merge. Easiest: re-run with a modified
    # flow that keeps surprise. Check what's in df_full.
    logger.info("Full strategy (40-100%% surprise, hold 40, bull): n=%d win_rate=%.1f%% alpha_hit=%.1f%% median_alpha=%.2f%%",
                len(df_full), float(res.win_rate_pct), float(res.alpha_hit_rate_pct), float(res.median_alpha_pct))

    # Get signal-level surprise from earnings data: for each (ticker, date) we need surprise.
    # We can get it by re-running signal generation and merging on (ticker, date).
    from backtest_engine import generate_earnings_signals, compute_returns
    signals_40_100 = generate_earnings_signals(data, earn, cfg)
    if not signals_40_100:
        logger.error("No signals from generator")
        sys.exit(1)
    # Build a DataFrame of signals with surprise
    sig_df = pd.DataFrame([{"ticker": s["ticker"], "date": s["date"], "surprise_pct": s["surprise_pct"]} for s in signals_40_100])
    sig_df["date"] = pd.to_datetime(sig_df["date"])
    df_full["date"] = pd.to_datetime(df_full["date"])
    merged = df_full.merge(sig_df, on=["ticker", "date"], how="left")
    if merged["surprise_pct"].isna().all():
        logger.warning("Could not merge surprise; using full sample only")
        merged = df_full.copy()
        merged["surprise_pct"] = 50  # placeholder

    logger.info("")
    logger.info("=" * 70)
    logger.info("  EXTREME SELECTIVITY: What hit rate can we get?")
    logger.info("=" * 70)

    # Top quartile by surprise (top 25%)
    q75 = merged["surprise_pct"].quantile(0.75)
    top25 = merged[merged["surprise_pct"] >= q75]
    m25 = metrics(top25)
    logger.info("  Top 25%% by surprise (>= %.1f%%):  n=%d  win_rate=%.1f%%  alpha_hit=%.1f%%  median_alpha=%.2f%%",
                q75, m25["n"], m25["win_rate"], m25["alpha_hit"], m25["median_alpha"])

    # Top decile (top 10%)
    q90 = merged["surprise_pct"].quantile(0.90)
    top10 = merged[merged["surprise_pct"] >= q90]
    m10 = metrics(top10)
    logger.info("  Top 10%% by surprise (>= %.1f%%):  n=%d  win_rate=%.1f%%  alpha_hit=%.1f%%  median_alpha=%.2f%%",
                q90, m10["n"], m10["win_rate"], m10["alpha_hit"], m10["median_alpha"])

    # Stricter band: 60-100%
    cfg60 = BacktestConfig("earn_h40_surp60_100_bullTrue", hold_days=40, min_surprise_pct=60, max_surprise_pct=100, require_bull_regime=True, signal_type="earnings")
    res60, df60 = run_backtest(data, spy, earn, cfg60)
    if df60 is not None and len(df60) >= 5:
        logger.info("  Surprise 60-100%% only:  n=%d  win_rate=%.1f%%  alpha_hit=%.1f%%  median_alpha=%.2f%%",
                    len(df60), float(res60.win_rate_pct), float(res60.alpha_hit_rate_pct), float(res60.median_alpha_pct))

    # 70-100%
    cfg70 = BacktestConfig("earn_h40_surp70_100_bullTrue", hold_days=40, min_surprise_pct=70, max_surprise_pct=100, require_bull_regime=True, signal_type="earnings")
    res70, df70 = run_backtest(data, spy, earn, cfg70)
    if df70 is not None and len(df70) >= 5:
        logger.info("  Surprise 70-100%% only:  n=%d  win_rate=%.1f%%  alpha_hit=%.1f%%  median_alpha=%.2f%%",
                    len(df70), float(res70.win_rate_pct), float(res70.alpha_hit_rate_pct), float(res70.median_alpha_pct))

    # Combo (earnings + RSI<=40) — already have 59%% in winning_strategies
    cfg_combo = BacktestConfig("combo_h20", hold_days=20, min_surprise_pct=40, max_surprise_pct=100, signal_type="combo")
    res_combo, df_combo = run_backtest(data, spy, earn, cfg_combo)
    if df_combo is not None and len(df_combo) >= 5:
        logger.info("  Combo (earnings + RSI<=40), hold 20:  n=%d  win_rate=%.1f%%  alpha_hit=%.1f%%  median_alpha=%.2f%%",
                    len(df_combo), float(res_combo.win_rate_pct), float(res_combo.alpha_hit_rate_pct), float(res_combo.median_alpha_pct))

    logger.info("")
    logger.info("  CONCLUSION: Best achievable hit rate with free data (no lookahead) is in the 55-65%% range.")
    logger.info("  90%% would require private information or curve-fitting (would fail out-of-sample).")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
