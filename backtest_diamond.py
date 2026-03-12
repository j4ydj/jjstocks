#!/usr/bin/env python3
"""
Backtest diamond (Market Cipher) variants until we find one that passes the engine bar.

Tries:
  - Diamond + bull regime + hold 40d (match winning strategy hold/regime)
  - Stricter green (wave < -70)
  - Diamond + step 7 days (fewer signals)
  - Diamond_combo: green diamond only when recent earnings beat (20% or 40%) in last 60d
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

UNI = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "CRWD", "DDOG", "SOFI",
    "CELH", "CAVA", "ELF", "ONON", "TGTX", "RKLB", "HOOD", "AFRM", "FUBO", "PLUG",
    "JPM", "V", "UNH", "JNJ", "HD", "WMT", "DIS", "NKE", "PEP", "KO", "XOM", "CRM",
]

CONFIGS = [
    BacktestConfig("diamond_hold40_bull", hold_days=40, signal_type="diamond", require_bull_regime=True),
    BacktestConfig("diamond_hold20_bull", hold_days=20, signal_type="diamond", require_bull_regime=True),
    BacktestConfig("diamond_strict70_hold40_bull", hold_days=40, signal_type="diamond", require_bull_regime=True, diamond_green_thresh=-70),
    BacktestConfig("diamond_step7_hold40_bull", hold_days=40, signal_type="diamond", require_bull_regime=True, diamond_step_days=7),
    BacktestConfig("diamond_combo_surp20_hold40_bull", hold_days=40, signal_type="diamond_combo", require_bull_regime=True, min_surprise_pct=20),
    BacktestConfig("diamond_combo_surp40_hold40_bull", hold_days=40, signal_type="diamond_combo", require_bull_regime=True, min_surprise_pct=40),
    # Winning strategy (earnings 40-100%, bull, 40d) filtered by green diamond within 10d of entry
    BacktestConfig("earnings_diamond_40_100_hold40_bull", hold_days=40, signal_type="earnings_diamond", require_bull_regime=True, min_surprise_pct=40, max_surprise_pct=100),
]


def main():
    logger.info("Searching for a diamond variant that passes the engine bar")
    logger.info("")

    data, spy = fetch_and_cache_prices(UNI, days=756)
    if len(data) < 5:
        logger.error("Too few tickers loaded (%d).", len(data))
        sys.exit(1)
    logger.info("Loaded %d tickers + SPY", len(data))

    earn = load_earnings_history(list(data.keys()))
    logger.info("Earnings history for %d tickers (for diamond_combo)", len(earn))
    logger.info("")

    best = None
    passed = []

    for cfg in CONFIGS:
        res, _ = run_backtest(data, spy, earn, cfg)
        logger.info("%-35s n=%4d  med_alpha=%+6.2f%%  alpha_hit=%5.1f%%  win=%5.1f%%  passed=%s",
                    cfg.name, res.n_signals, res.median_alpha_pct, res.alpha_hit_rate_pct, res.win_rate_pct, res.passed)
        if res.passed:
            passed.append((cfg, res))
        if best is None or (res.n_signals >= 30 and res.median_alpha_pct > (best[1].median_alpha_pct if best[1].n_signals >= 30 else -999)):
            best = (cfg, res)

    logger.info("")
    logger.info("=" * 60)
    if passed:
        logger.info("  PASSED (%d): %s", len(passed), [c.name for c, r in passed])
        best_p = max(passed, key=lambda x: x[1].median_alpha_pct)
        logger.info("  Best passed: %s  median_alpha=%.2f%%  alpha_hit=%.1f%%",
                    best_p[0].name, best_p[1].median_alpha_pct, best_p[1].alpha_hit_rate_pct)
    else:
        logger.info("  No variant passed the engine bar.")
        if best and best[1].n_signals >= 15:
            logger.info("  Best by median alpha (n>=15): %s  med_alpha=%.2f%%  alpha_hit=%.1f%%  n=%d",
                        best[0].name, best[1].median_alpha_pct, best[1].alpha_hit_rate_pct, best[1].n_signals)
    logger.info("=" * 60)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
