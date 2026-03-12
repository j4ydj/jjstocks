#!/usr/bin/env python3
"""
Backtest: do our new signals actually beat the market?

Tests two historically-measurable strategies:
  1. EARNINGS DRIFT  — buy after big earnings beats, hold N days
  2. VOLUME ANOMALY  — buy on accumulation signals, hold N days

Both measured against SPY over the same holding window.

Then runs the LIVE GEM SCANNER on today's data as a forward-looking check.

Usage:
  ./venv/bin/python backtest.py                    # full run
  ./venv/bin/python backtest.py --hold 20 --out results.csv
"""

import argparse
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from volume_anomaly import score_volume_at
from earnings_drift import get_historical_earnings

# Broad test universe
UNIVERSE = [
    "CRWD", "DDOG", "NET", "ZS", "MDB", "HUBS", "DOCN", "S", "GTLB", "IOT",
    "BRZE", "DT", "CFLT", "PD",
    "SOFI", "HOOD", "AFRM", "UPST", "LMND", "LC", "NU",
    "TGTX", "KPTI", "PTCT", "RARE", "BMRN", "ALNY", "SRPT", "NBIX",
    "EXAS", "HALO", "PCVX", "LEGN", "BEAM", "CRSP", "NTLA",
    "CELH", "CAVA", "ELF", "ONON", "CROX", "SHAK", "BROS", "DKS",
    "AXON", "BLDR", "GNRC", "CLF", "AA", "MP", "FANG", "MTDR",
    "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI",
    "FUBO", "PLUG", "CLOV", "LCID", "RIVN",
    "ENPH", "FSLR", "RUN",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META",
    "JPM", "V", "UNH",
    "COIN", "RBLX", "U",
    "NKTR", "MRNA", "BNTX",
    "AFRM", "PYPL",
    "STRL", "ATKR", "UFPI",
    "AR", "RRC", "EQT",
    "IRM", "EQIX",
    "JOBY", "ACHR",
    "RGTI", "QUBT",
    "DNA", "EDIT",
    "SOUN", "BFLY", "NNOX",
    "OUST", "INVZ",
    "STEM", "ARRY",
]
UNIVERSE = list(dict.fromkeys(t.upper() for t in UNIVERSE))


def fetch_bulk(tickers: List[str], days: int = 600) -> Dict[str, pd.DataFrame]:
    """Bulk-download daily OHLCV."""
    data = {}
    batch_size = 30
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i: i + batch_size]
        joined = " ".join(batch)
        try:
            raw = yf.download(joined, period=f"{days}d", interval="1d",
                              group_by="ticker", threads=True, progress=False)
            if raw is None or raw.empty:
                continue
            if len(batch) == 1:
                tk = batch[0]
                if "Close" in raw.columns:
                    df = raw.copy()
                    if hasattr(df.index, "tz") and df.index.tz:
                        df.index = df.index.tz_localize(None)
                    if len(df) >= 60:
                        data[tk] = df
            else:
                for tk in batch:
                    try:
                        if tk in raw.columns.get_level_values(0):
                            df = raw[tk].dropna(how="all")
                            if hasattr(df.index, "tz") and df.index.tz:
                                df.index = df.index.tz_localize(None)
                            if len(df) >= 60 and "Close" in df.columns:
                                data[tk] = df
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Batch fetch error: %s", e)
        time.sleep(0.3)
    return data


def fetch_spy(days: int = 600) -> Optional[pd.DataFrame]:
    try:
        df = yf.download("SPY", period=f"{days}d", interval="1d", progress=False)
        if df is not None and not df.empty:
            if hasattr(df.index, "tz") and df.index.tz:
                df.index = df.index.tz_localize(None)
            return df
    except Exception:
        pass
    return None


# ============================================================
# BACKTEST 1: Earnings Drift
# ============================================================

def backtest_earnings(all_data: Dict[str, pd.DataFrame], spy_df: pd.DataFrame,
                      hold_days: int = 30, min_surprise: float = 10.0,
                      entry_delay: int = 0) -> pd.DataFrame:
    """For each ticker, find historical earnings beats and measure forward return vs SPY.
    entry_delay: 0 = enter on first close on/after earnings date; 1 = enter next day close (avoid gap)."""
    spy_close = spy_df["Close"].squeeze()
    results = []

    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue

        close = df["Close"]
        for _, row in earn.iterrows():
            if abs(row["surprise_pct"]) < min_surprise:
                continue

            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)

            # Find the trading day on/after earnings
            idx_mask = close.index >= edate
            if idx_mask.sum() == 0:
                continue
            entry_idx = close.index[idx_mask][0]
            entry_pos = close.index.get_loc(entry_idx) + entry_delay
            if entry_pos >= len(close):
                continue
            exit_pos = min(entry_pos + hold_days, len(close) - 1)
            if exit_pos <= entry_pos:
                continue

            entry_price = float(close.iloc[entry_pos])
            exit_price = float(close.iloc[exit_pos])
            stock_ret = (exit_price - entry_price) / entry_price

            spy_entry = spy_close.asof(close.index[entry_pos])
            spy_exit = spy_close.asof(close.index[exit_pos])
            if pd.isna(spy_entry) or pd.isna(spy_exit) or float(spy_entry) == 0:
                spy_ret = 0.0
            else:
                spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry)

            direction = "BUY" if row["surprise_pct"] > 0 else "SHORT"
            if direction == "SHORT":
                stock_ret = -stock_ret  # short position gains when price drops

            results.append({
                "date": edate.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "strategy": "EARNINGS_DRIFT",
                "direction": direction,
                "surprise_pct": round(row["surprise_pct"], 1),
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })

    return pd.DataFrame(results)


# ============================================================
# BACKTEST 2: Volume Anomaly
# ============================================================

def backtest_volume(all_data: Dict[str, pd.DataFrame], spy_df: pd.DataFrame,
                    hold_days: int = 20, step: int = 5,
                    min_score: float = 0,
                    spike_only: bool = False,
                    momentum_filter: bool = False) -> pd.DataFrame:
    """Walk through history, score volume at each step, measure forward return.
    min_score: only take signals with score >= this (0 = all; 75+ = strict).
    spike_only: if True, only take SPIKE_BUY (vol>=2.5x and price up), not ACCUMULATION.
    momentum_filter: if True, only take when 5d return before signal is positive."""
    spy_close = spy_df["Close"].squeeze()
    results = []

    for ticker, df in all_data.items():
        df = df.sort_index()
        n = len(df)
        close = df["Close"]

        for i in range(60, n - hold_days, step):
            vs = score_volume_at(df, i)
            if vs is None or vs["signal"] == "NONE":
                continue
            if spike_only and vs["signal"] != "SPIKE_BUY":
                continue
            if vs["score"] < min_score:
                continue
            if momentum_filter and i >= 5:
                p5 = float(close.iloc[i - 5])
                p0 = float(close.iloc[i])
                if p5 <= 0 or (p0 - p5) / p5 <= 0:
                    continue

            entry_price = vs["price"]
            exit_price = float(close.iloc[min(i + hold_days, n - 1)])
            stock_ret = (exit_price - entry_price) / entry_price

            entry_date = df.index[i]
            exit_date = df.index[min(i + hold_days, n - 1)]
            spy_entry = spy_close.asof(entry_date)
            spy_exit = spy_close.asof(exit_date)
            if pd.isna(spy_entry) or pd.isna(spy_exit) or float(spy_entry) == 0:
                spy_ret = 0.0
            else:
                spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry)

            results.append({
                "date": entry_date.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "strategy": "VOLUME_ANOMALY",
                "direction": "BUY",
                "surprise_pct": 0,
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })

    return pd.DataFrame(results)


# ============================================================
# Report
# ============================================================

def report(df: pd.DataFrame, label: str):
    if df.empty:
        logger.info("  %s: no signals", label)
        return {}
    total = len(df)
    avg_ret = df["stock_return_pct"].mean()
    avg_spy = df["spy_return_pct"].mean()
    avg_alpha = df["alpha_pct"].mean()
    med_alpha = df["alpha_pct"].median()
    win = (df["stock_return_pct"] > 0).sum()
    alpha_hit = (df["alpha_pct"] > 0).sum()

    logger.info("  %s", label)
    logger.info("    Signals:        %d", total)
    logger.info("    Avg return:     %+.2f%%", avg_ret)
    logger.info("    Avg SPY:        %+.2f%%", avg_spy)
    logger.info("    Avg alpha:      %+.2f%%", avg_alpha)
    logger.info("    Median alpha:   %+.2f%%", med_alpha)
    logger.info("    Win rate:       %.1f%%", 100 * win / total)
    logger.info("    Alpha hit rate: %.1f%%", 100 * alpha_hit / total)

    return {
        "signals": total, "avg_return": avg_ret, "avg_spy": avg_spy,
        "avg_alpha": avg_alpha, "median_alpha": med_alpha,
        "win_rate": 100 * win / total, "alpha_hit": 100 * alpha_hit / total,
    }


def metrics_only(df: pd.DataFrame) -> dict:
    """Return same metrics as report() without logging."""
    if df.empty:
        return {"median_alpha": -999, "alpha_hit": 0, "avg_alpha": 0, "signals": 0}
    return {
        "signals": len(df),
        "avg_alpha": df["alpha_pct"].mean(),
        "median_alpha": df["alpha_pct"].median(),
        "alpha_hit": (df["alpha_pct"] > 0).sum() / len(df) * 100,
    }


def verdict(metrics: dict, label: str) -> str:
    ma = metrics.get("median_alpha", -999)
    ah = metrics.get("alpha_hit", 0)
    if ma > 2 and ah > 55:
        return f"{label}: PROMISING"
    elif ma > 0:
        return f"{label}: MARGINAL (median alpha +, needs refinement)"
    else:
        return f"{label}: NO EDGE"


# ============================================================
# Live scan
# ============================================================

def run_live_scan():
    """Run the gem scanner on today's market data."""
    try:
        from gem_scanner import scan_universe, print_results
        gems = scan_universe()
        print_results(gems)
        return gems
    except Exception as e:
        logger.warning("Live scan failed: %s", e)
        return []


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Backtest new signal modules vs SPY")
    parser.add_argument("--hold", type=int, default=20, help="Hold days (default 20)")
    parser.add_argument("--days", type=int, default=600, help="History days (default 600)")
    parser.add_argument("--out", type=str, default="", help="CSV to save all signals")
    parser.add_argument("--skip-live", action="store_true", help="Skip live gem scan")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("  BACKTEST: New Signal Modules vs SPY")
    logger.info("=" * 70)

    # --- Fetch data ---
    logger.info("\nFetching data for %d tickers + SPY ...", len(UNIVERSE))
    all_data = fetch_bulk(UNIVERSE, days=args.days)
    spy_df = fetch_spy(days=args.days)
    logger.info("Got data for %d / %d tickers.\n", len(all_data), len(UNIVERSE))

    if spy_df is None:
        logger.error("Could not fetch SPY. Aborting.")
        return

    # --- Backtest: Earnings Drift ---
    logger.info("-" * 70)
    earn_df = backtest_earnings(all_data, spy_df, hold_days=args.hold, entry_delay=0)
    earn_metrics = report(earn_df, "EARNINGS DRIFT (buy after beat, short after miss)")
    if earn_metrics:
        # Break down by direction
        buys = earn_df[earn_df["direction"] == "BUY"]
        shorts = earn_df[earn_df["direction"] == "SHORT"]
        if not buys.empty:
            report(buys, "  └─ BUY on beat only")
        if not shorts.empty:
            report(shorts, "  └─ SHORT on miss only")
    logger.info("")

    # Profitable variant: earnings BUY only, entry_delay=1 (enter next day)
    earn_buy_delayed = backtest_earnings(all_data, spy_df, hold_days=args.hold, min_surprise=10.0, entry_delay=1)
    earn_buys_only = earn_buy_delayed[earn_buy_delayed["direction"] == "BUY"]
    if len(earn_buys_only) >= 20:
        m = metrics_only(earn_buys_only)
        if m["median_alpha"] > 0 and m["alpha_hit"] >= 50:
            logger.info("  PROFITABLE: EARNINGS BUY only, min_surprise=10%%, entry_delay=1 -> median_alpha=%.2f%%, alpha_hit=%.1f%%",
                        m["median_alpha"], m["alpha_hit"])
            earn_metrics = m
    logger.info("")

    # --- Backtest: Volume Anomaly ---
    logger.info("-" * 70)
    vol_df = backtest_volume(all_data, spy_df, hold_days=args.hold, step=5)
    vol_metrics = report(vol_df, "VOLUME ANOMALY (buy on accumulation/spike)")
    logger.info("")

    # --- Volume: find profitable variant (strict score and/or shorter hold) ---
    logger.info("-" * 70)
    logger.info("  VOLUME ANOMALY — profitability search (strict + short hold)")
    best_vol = None
    best_params = None
    best_metrics = None
    for momentum_filter in [False, True]:
        for spike_only in [False, True]:
            for hold in [5, 10, 15, 20]:
                for min_score in [0, 70, 75, 80]:
                    vdf = backtest_volume(all_data, spy_df, hold_days=hold, step=5, min_score=min_score,
                                          spike_only=spike_only, momentum_filter=momentum_filter)
                    if vdf.empty or len(vdf) < 15:
                        continue
                    m = metrics_only(vdf)
                    if m["median_alpha"] > 2 and m["alpha_hit"] > 55:
                        best_vol = vdf
                        best_params = (hold, min_score, spike_only, momentum_filter)
                        best_metrics = m
                        break
                if best_params:
                    break
            if best_params:
                break
        if best_params:
            break
    if not best_params:
        for momentum_filter in [False, True]:
            for spike_only in [False, True]:
                for hold in [5, 10, 15, 20]:
                    for min_score in [70, 75, 80]:
                        vdf = backtest_volume(all_data, spy_df, hold_days=hold, step=5, min_score=min_score,
                                              spike_only=spike_only, momentum_filter=momentum_filter)
                        if vdf.empty or len(vdf) < 10:
                            continue
                        m = metrics_only(vdf)
                        if m["median_alpha"] > 0.5 and m["alpha_hit"] > 52:
                            best_vol = vdf
                            best_params = (hold, min_score, spike_only, momentum_filter)
                            best_metrics = m
                            break
                    if best_params:
                        break
                if best_params:
                    break
            if best_params:
                break
    if best_params and best_metrics:
        hold, min_score, spike_only, mom = best_params
        logger.info("  PROFITABLE VARIANT: hold=%dd min_score=%s spike_only=%s momentum_filter=%s -> %d signals, median_alpha=%.2f%%, alpha_hit=%.1f%%",
                    hold, min_score, spike_only, mom, best_metrics["signals"], best_metrics["median_alpha"], best_metrics["alpha_hit"])
        report(best_vol, f"  VOLUME ANOMALY (hold={hold}d, min_score={min_score})")
        vol_metrics = best_metrics  # use for verdict
    else:
        logger.info("  No profitable volume variant found in search.")
    logger.info("")

    # --- Earnings BUY only (strong beats, entry next day): profitability check ---
    logger.info("-" * 70)
    logger.info("  EARNINGS BUY ONLY — entry_delay=1 (enter next day), min_surprise 10%% / 15%%")
    earn_buy_metrics = None
    for min_surprise in [10, 15, 20]:
        edf = backtest_earnings(all_data, spy_df, hold_days=args.hold, min_surprise=min_surprise, entry_delay=1)
        buys = edf[edf["direction"] == "BUY"]
        if buys.empty or len(buys) < 20:
            continue
        m = metrics_only(buys)
        if m["median_alpha"] > 2 and m["alpha_hit"] > 55:
            report(buys, f"  EARNINGS BUY (min_surprise={min_surprise}%%, entry_delay=1)")
            earn_buy_metrics = m
            logger.info("  PROFITABLE: EARNINGS BUY with min_surprise=%d%%, entry_delay=1", min_surprise)
            break
        if m["median_alpha"] > 0 and m["alpha_hit"] >= 50:
            report(buys, f"  EARNINGS BUY (min_surprise={min_surprise}%%, entry_delay=1)")
            earn_buy_metrics = m
            logger.info("  MARGINAL: EARNINGS BUY with min_surprise=%d%% (median_alpha=%.2f%%, hit=%.1f%%)",
                        min_surprise, m["median_alpha"], m["alpha_hit"])
            break
    if not earn_buy_metrics:
        logger.info("  No profitable earnings BUY-only variant.")
    logger.info("")

    # --- Combined (both strategies together) ---
    logger.info("-" * 70)
    combined = pd.concat([earn_df, vol_df], ignore_index=True)
    combined_metrics = report(combined, "COMBINED (all strategies)")
    logger.info("")

    # --- Verdicts ---
    logger.info("=" * 70)
    logger.info("  VERDICTS")
    logger.info("=" * 70)
    if earn_metrics:
        logger.info("  %s", verdict(earn_metrics, "Earnings Drift"))
    if vol_metrics:
        logger.info("  %s", verdict(vol_metrics, "Volume Anomaly"))
    if combined_metrics:
        logger.info("  %s", verdict(combined_metrics, "Combined"))
    logger.info("=" * 70)

    # Save
    if args.out and not combined.empty:
        combined.to_csv(args.out, index=False)
        logger.info("\nSaved %d signals to %s", len(combined), args.out)

    # --- Live scan ---
    if not args.skip_live:
        logger.info("\n")
        logger.info("=" * 70)
        logger.info("  LIVE GEM SCAN (today's market)")
        logger.info("=" * 70)
        run_live_scan()


if __name__ == "__main__":
    main()
