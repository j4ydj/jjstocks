#!/usr/bin/env python3
"""
Run agenda experiments: red-diamond exclusion, consumer_industrials-only universe,
hold-period sweep. Extends research without being asked.
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest_engine import (
    BacktestConfig,
    fetch_and_cache_prices,
    load_earnings_history,
    run_backtest,
)

# Same mixed universe as original winning strategy
UNI = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "CRWD", "DDOG", "SOFI",
    "CELH", "CAVA", "ELF", "ONON", "TGTX", "RKLB", "HOOD", "AFRM", "FUBO", "PLUG",
    "JPM", "V", "UNH", "JNJ", "HD", "WMT", "DIS", "NKE", "PEP", "KO", "XOM", "CRM",
]

# Consumer/industrials segment (best in all_markets)
CONSUMER_INDUSTRIALS = [
    "WMT", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "COST", "DG",
    "CELH", "CAVA", "ELF", "ONON", "CROX", "SHAK", "BROS", "DKS",
    "AXON", "BLDR", "GNRC", "CAT", "DE", "LMT", "RTX", "HII", "GD",
    "STRL", "ATKR", "UFPI", "FAST", "CARR", "OTIS", "JCI",
]


def run_one(data, spy, earn, cfg):
    res, _ = run_backtest(data, spy, earn, cfg)
    return res


def main():
    logger.info("Research agenda: extending experiments")
    logger.info("")

    # Load once for mixed universe
    data, spy = fetch_and_cache_prices(UNI, days=756)
    if len(data) < 10:
        logger.error("Too few tickers: %d", len(data))
        return 1
    earn = load_earnings_history(list(data.keys()))
    logger.info("Loaded %d tickers + SPY, earnings for %d", len(data), len(earn))
    logger.info("")

    base_cfg = BacktestConfig(
        name="earn_40_100_40d_bull",
        hold_days=40,
        min_surprise_pct=40,
        max_surprise_pct=100,
        require_bull_regime=True,
        signal_type="earnings",
    )

    # 1) Baseline
    logger.info("1) Baseline (earnings 40-100%%, hold 40d, bull)")
    r0 = run_one(data, spy, earn, base_cfg)
    logger.info("   n=%d  med_alpha=%.2f%%  alpha_hit=%.1f%%  passed=%s",
                r0.n_signals, r0.median_alpha_pct, r0.alpha_hit_rate_pct, r0.passed)
    logger.info("")

    # 2) Exclude entries when red/blood diamond in last 5 days
    logger.info("2) Same but exclude if red/blood diamond in 5d before entry")
    cfg_no_red = BacktestConfig(
        name="earn_40_100_40d_bull_no_red_diamond",
        hold_days=40,
        min_surprise_pct=40,
        max_surprise_pct=100,
        require_bull_regime=True,
        signal_type="earnings_no_red_diamond",
    )
    r1 = run_one(data, spy, earn, cfg_no_red)
    logger.info("   n=%d  med_alpha=%.2f%%  alpha_hit=%.1f%%  passed=%s",
                r1.n_signals, r1.median_alpha_pct, r1.alpha_hit_rate_pct, r1.passed)
    if r1.n_signals > 0:
        logger.info("   vs baseline: med_alpha %+.2f%%  alpha_hit %+.1f%%",
                    r1.median_alpha_pct - r0.median_alpha_pct,
                    r1.alpha_hit_rate_pct - r0.alpha_hit_rate_pct)
    logger.info("")

    # 3) Consumer/industrials-only universe
    logger.info("3) Same strategy on consumer_industrials-only universe")
    data_ci, spy_ci = fetch_and_cache_prices(CONSUMER_INDUSTRIALS, days=756)
    earn_ci = load_earnings_history(list(data_ci.keys()))
    r2 = run_one(data_ci, spy_ci, earn_ci, base_cfg)
    logger.info("   n=%d  med_alpha=%.2f%%  alpha_hit=%.1f%%  passed=%s",
                r2.n_signals, r2.median_alpha_pct, r2.alpha_hit_rate_pct, r2.passed)
    logger.info("")

    # 4) Hold period sweep
    logger.info("4) Hold period sweep (20, 30, 40, 50, 60)")
    for hold in [20, 30, 40, 50, 60]:
        c = BacktestConfig(
            name=f"hold{hold}",
            hold_days=hold,
            min_surprise_pct=40,
            max_surprise_pct=100,
            require_bull_regime=True,
            signal_type="earnings",
        )
        r = run_one(data, spy, earn, c)
        logger.info("   hold=%2d  n=%3d  med_alpha=%+6.2f%%  alpha_hit=%5.1f%%",
                    hold, r.n_signals, r.median_alpha_pct, r.alpha_hit_rate_pct)
    logger.info("")

    # 5) Surprise band sweep
    logger.info("5) Surprise band sweep")
    for (lo, hi) in [(30, 80), (40, 100), (50, 120), (40, 150)]:
        c = BacktestConfig(
            name=f"surp{lo}_{hi}",
            hold_days=40,
            min_surprise_pct=lo,
            max_surprise_pct=hi,
            require_bull_regime=True,
            signal_type="earnings",
        )
        r = run_one(data, spy, earn, c)
        logger.info("   surprise %d-%d%%  n=%3d  med_alpha=%+6.2f%%  alpha_hit=%5.1f%%",
                    lo, hi, r.n_signals, r.median_alpha_pct, r.alpha_hit_rate_pct)

    logger.info("")
    logger.info("Done. Update RESEARCH_AGENDA.md §5 with these results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
