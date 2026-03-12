#!/usr/bin/env python3
"""
Quick profitability check: load data once, test only promising variants.
Run: ./venv/bin/python backtest_profitable.py
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Reuse backtest data and functions
from backtest import (
    UNIVERSE,
    fetch_bulk,
    fetch_spy,
    backtest_earnings,
    backtest_volume,
    metrics_only,
    report,
)

def main():
    logger.info("Loading data (once)...")
    all_data = fetch_bulk(UNIVERSE, days=600)
    spy_df = fetch_spy(days=600)
    if spy_df is None:
        logger.error("No SPY")
        return 1
    logger.info("Loaded %d tickers.\n", len(all_data))

    # 1) Earnings BUY only, various min_surprise (entry next day to avoid gap)
    logger.info("--- EARNINGS BUY ONLY (entry next day) ---")
    for min_surprise in [10, 12, 15, 20, 25]:
        edf = backtest_earnings(all_data, spy_df, hold_days=40, min_surprise=min_surprise, entry_delay=1)
        buys = edf[edf["direction"] == "BUY"]
        if len(buys) < 15:
            continue
        m = metrics_only(buys)
        ok = m["median_alpha"] > 0 and m["alpha_hit"] >= 50
        logger.info("  min_surprise=%d%%  n=%d  median_alpha=%.2f%%  alpha_hit=%.1f%%  %s",
                    min_surprise, m["signals"], m["median_alpha"], m["alpha_hit"], "PROFITABLE" if ok else "")
        if ok:
            report(buys, f"  EARNINGS BUY (min_surprise={min_surprise}%%, entry_delay=1)")
            logger.info("  >>> USE: earnings BUY only, min_surprise=%d%%, hold 40d, entry_delay=1\n", min_surprise)
            return 0

    # 2) Volume with momentum filter (only when 5d return > 0)
    logger.info("--- VOLUME (momentum_filter=True) ---")
    for hold in [5, 10, 15, 20]:
        for min_score in [0, 65, 70, 75]:
            vdf = backtest_volume(all_data, spy_df, hold_days=hold, step=10, min_score=min_score,
                                  spike_only=False, momentum_filter=True)
            if len(vdf) < 15:
                continue
            m = metrics_only(vdf)
            ok = m["median_alpha"] > 0 and m["alpha_hit"] >= 50
            logger.info("  hold=%dd min_score=%s  n=%d  median_alpha=%.2f%%  alpha_hit=%.1f%%  %s",
                        hold, min_score, m["signals"], m["median_alpha"], m["alpha_hit"], "PROFITABLE" if ok else "")
            if ok:
                report(vdf, f"  VOLUME (hold={hold}d, min_score={min_score}, momentum_filter)")
                logger.info("  >>> USE: volume hold=%dd min_score=%s momentum_filter\n", hold, min_score)
                return 0

    # 3) Volume SPIKE only (high vol + price up)
    logger.info("--- VOLUME SPIKE ONLY ---")
    for hold in [5, 10, 20]:
        vdf = backtest_volume(all_data, spy_df, hold_days=hold, step=10, min_score=0,
                              spike_only=True, momentum_filter=False)
        if len(vdf) < 10:
            continue
        m = metrics_only(vdf)
        ok = m["median_alpha"] > 0 and m["alpha_hit"] >= 50
        logger.info("  hold=%dd  n=%d  median_alpha=%.2f%%  alpha_hit=%.1f%%  %s",
                    hold, m["signals"], m["median_alpha"], m["alpha_hit"], "PROFITABLE" if ok else "")
        if ok:
            report(vdf, f"  VOLUME SPIKE (hold={hold}d)")
            logger.info("  >>> USE: volume spike_only hold=%dd\n", hold)
            return 0

    logger.info("\nNo profitable variant found in quick check.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
