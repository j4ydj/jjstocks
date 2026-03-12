#!/usr/bin/env python3
"""
Search for strategies that approach 80% alpha hit rate.

Uses full strategy_search universe. Stacks: earnings band + bull + no red diamond +
optional top-% by surprise + hold 20/30. Relaxes min_signals to 15 for "80% mode"
so we can find high-hit-rate configs even with fewer signals.
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest_engine import (
    BacktestConfig,
    fetch_and_cache_prices,
    load_earnings_history,
    run_backtest,
    BacktestResult,
)

# Full universe from strategy_search (80+ names)
UNIVERSE = [
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
UNIVERSE = list(dict.fromkeys(u.upper() for u in UNIVERSE))

TARGET_ALPHA_HIT = 80.0
MIN_SIGNALS_80_MODE = 10  # allow smaller n to find 80% configs


def build_80_configs():
    """Strict configs aimed at high alpha hit rate."""
    configs = []
    for hold in [20, 30]:
        for (lo, hi) in [(40, 100), (50, 100), (60, 100), (70, 100), (80, 100)]:
            for no_red in [False, True]:
                for top_pct in [None, 0.5, 0.33, 0.25, 0.10]:
                    name = f"earn_h{hold}_surp{lo}_{hi}_bull_no_red{no_red}"
                    if top_pct:
                        name += f"_top{int(top_pct*100)}pct"
                    cfg = BacktestConfig(
                        name=name,
                        hold_days=hold,
                        min_surprise_pct=float(lo),
                        max_surprise_pct=float(hi),
                        require_bull_regime=True,
                        signal_type="earnings_no_red_diamond" if no_red else "earnings",
                        earnings_top_pct_surprise=top_pct,
                    )
                    configs.append(cfg)
    return configs


def main():
    logger.info("Loading data (full universe %d tickers) ...", len(UNIVERSE))
    data, spy = fetch_and_cache_prices(UNIVERSE, days=756)
    tickers = list(data.keys())
    earn = load_earnings_history(tickers)
    logger.info("Tickers: %d, with earnings: %d", len(tickers), len(earn))
    logger.info("")

    configs = build_80_configs()
    logger.info("Running %d configs (target alpha hit >= 80%%, min_signals >= %d for 80%% mode) ...",
                len(configs), MIN_SIGNALS_80_MODE)
    logger.info("")

    import backtest_engine as be
    orig_min = be.MIN_SIGNALS
    be.MIN_SIGNALS = MIN_SIGNALS_80_MODE

    candidates = []
    for cfg in configs:
        res, _ = run_backtest(data, spy, earn, cfg)
        if res.n_signals >= MIN_SIGNALS_80_MODE and res.alpha_hit_rate_pct >= 70:
            candidates.append(res)
        if res.alpha_hit_rate_pct >= TARGET_ALPHA_HIT and res.n_signals >= MIN_SIGNALS_80_MODE:
            logger.info("  HIT 80%%+  %s  n=%d  alpha_hit=%.1f%%  med_alpha=%.2f%%",
                        cfg.name, res.n_signals, res.alpha_hit_rate_pct, res.median_alpha_pct)

    be.MIN_SIGNALS = orig_min

    candidates.sort(key=lambda r: (r.alpha_hit_rate_pct, r.median_alpha_pct), reverse=True)
    top = candidates[:15]

    logger.info("")
    logger.info("=" * 70)
    logger.info("  TOP CONFIGS BY ALPHA HIT (>= 70%%, n>=%d)", MIN_SIGNALS_80_MODE)
    logger.info("=" * 70)
    if not top:
        logger.info("  None reached 70%% alpha hit with n>=%d. Showing best 10 by alpha hit (any n):", MIN_SIGNALS_80_MODE)
        all_res = []
        for cfg in configs:
            res, _ = run_backtest(data, spy, earn, cfg)
            if res.n_signals >= 5:
                all_res.append(res)
        all_res.sort(key=lambda r: (r.alpha_hit_rate_pct, r.median_alpha_pct), reverse=True)
        for r in all_res[:10]:
            logger.info("    %s  n=%d  alpha_hit=%.1f%%  med_alpha=%.2f%%",
                        r.config.name, r.n_signals, r.alpha_hit_rate_pct, r.median_alpha_pct)
    else:
        for r in top:
            logger.info("    %s  n=%d  alpha_hit=%.1f%%  med_alpha=%.2f%%  passed=%s",
                        r.config.name, r.n_signals, r.alpha_hit_rate_pct, r.median_alpha_pct, r.passed)
    logger.info("=" * 70)

    if top and top[0].alpha_hit_rate_pct >= 70:
        best = top[0]
        out = {
            "target_alpha_hit_pct": TARGET_ALPHA_HIT,
            "min_signals_80_mode": MIN_SIGNALS_80_MODE,
            "best_config": {
                "name": best.config.name,
                "hold_days": best.config.hold_days,
                "min_surprise_pct": best.config.min_surprise_pct,
                "max_surprise_pct": best.config.max_surprise_pct,
                "require_bull_regime": best.config.require_bull_regime,
                "signal_type": best.config.signal_type,
                "earnings_top_pct_surprise": getattr(best.config, "earnings_top_pct_surprise", None),
                "n_signals": best.n_signals,
                "median_alpha_pct": best.median_alpha_pct,
                "alpha_hit_rate_pct": best.alpha_hit_rate_pct,
                "win_rate_pct": best.win_rate_pct,
            },
        }
        os.makedirs("backtest_cache", exist_ok=True)
        with open("backtest_cache/strategy_80_mode.json", "w") as f:
            json.dump(out, f, indent=2)
        logger.info("Saved best 80%% mode to backtest_cache/strategy_80_mode.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
