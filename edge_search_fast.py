#!/usr/bin/env python3
"""
Fast Edge Search - Focused on high-conviction combinations
Tests specific hypotheses quickly.
"""
import logging
import sys
import pandas as pd
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest import (
    UNIVERSE, fetch_bulk, fetch_spy, backtest_earnings, metrics_only, report
)

def test_earnings_surprise_momentum(all_data, spy_df):
    """Hypothesis: Larger surprises have better drift, but with diminishing returns."""
    logger.info("\n--- HYPOTHESIS 1: Surprise magnitude tiers ---")
    results = []
    for min_surprise in [10, 15, 20, 30, 40, 50]:
        df = backtest_earnings(
            all_data, spy_df, hold_days=40, min_surprise=min_surprise, entry_delay=1
        )
        if df.empty or "surprise_pct" not in df.columns:
            continue
        df = df[df["direction"] == "BUY"]
        if len(df) < 15:
            continue
        m = metrics_only(df)
        results.append({
            "min": f">={min_surprise}%",
            "n": m["signals"],
            "med_alpha": m["median_alpha"],
            "hit": m["alpha_hit"],
        })
        if m["median_alpha"] > 0.5 and m["alpha_hit"] > 52:
            logger.info(
                f"  GOOD: >={min_surprise}% surprise | n={m['signals']} "
                f"med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
            )
    return results

def test_shorting_large_misses(all_data, spy_df):
    """Hypothesis: Large misses gap down then bounce - short the bounce."""
    logger.info("\n--- HYPOTHESIS 2: Short large misses (fade the bounce) ---")
    from earnings_drift import get_historical_earnings
    
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for miss_threshold in [-15, -20, -30]:
        for entry_delay in [1, 2, 3]:
            for hold_days in [5, 10, 15]:
                trades = []
                for ticker, df in all_data.items():
                    earn = get_historical_earnings(ticker, lookback_days=700)
                    if earn.empty:
                        continue
                    close = df["Close"]
                    
                    for _, row in earn.iterrows():
                        if row["surprise_pct"] > miss_threshold:  # Only large misses
                            continue
                        
                        edate = pd.Timestamp(row["date"])
                        if edate.tzinfo:
                            edate = edate.tz_localize(None)
                        
                        idx_mask = close.index >= edate
                        if idx_mask.sum() == 0:
                            continue
                        entry_idx = close.index[idx_mask][0]
                        entry_pos = close.index.get_loc(entry_idx) + entry_delay
                        if entry_pos >= len(close) - hold_days:
                            continue
                        
                        exit_pos = min(entry_pos + hold_days, len(close) - 1)
                        entry_price = float(close.iloc[entry_pos])
                        exit_price = float(close.iloc[exit_pos])
                        
                        # Short position
                        stock_ret = -((exit_price - entry_price) / entry_price)
                        spy_entry = spy_close.asof(close.index[entry_pos])
                        spy_exit = spy_close.asof(close.index[exit_pos])
                        spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
                        
                        trades.append({
                            "ticker": ticker,
                            "alpha_pct": (stock_ret - spy_ret) * 100,
                            "stock_ret": stock_ret * 100,
                            "spy_ret": spy_ret * 100,
                        })
                
                if len(trades) < 10:
                    continue
                df = pd.DataFrame(trades)
                m = metrics_only(df)
                if m["median_alpha"] > 1 and m["alpha_hit"] > 55:
                    logger.info(
                        f"  GREAT: miss<{miss_threshold}%, delay={entry_delay}d, hold={hold_days}d | "
                        f"n={m['signals']} med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
                    )
                    return {
                        "strategy": "short_large_misses",
                        "params": {"miss_threshold": miss_threshold, "entry_delay": entry_delay, "hold_days": hold_days},
                        "metrics": m,
                    }
    return None

def test_different_hold_periods(all_data, spy_df):
    """Hypothesis: Different hold periods work for different surprise sizes."""
    logger.info("\n--- HYPOTHESIS 3: Optimal hold periods by surprise size ---")
    
    for min_surprise in [10, 20, 30]:
        best = None
        best_hold = None
        for hold_days in [5, 10, 15, 20, 40, 60]:
            df = backtest_earnings(
                all_data, spy_df, hold_days=hold_days, min_surprise=min_surprise, entry_delay=1
            )
            df = df[df["direction"] == "BUY"]
            if len(df) < 10:
                continue
            m = metrics_only(df)
            if best is None or m["median_alpha"] > best["median_alpha"]:
                best = m
                best_hold = hold_days
        if best and best_hold:
            logger.info(
                f"  surprise>={min_surprise}%: best hold={best_hold}d | "
                f"n={best['signals']} med_alpha={best['median_alpha']:.2f}% hit={best['alpha_hit']:.1f}%"
            )

def test_weekly_patterns(all_data, spy_df):
    """Hypothesis: Earnings on certain days perform better."""
    logger.info("\n--- HYPOTHESIS 4: Earnings day-of-week effect ---")
    from earnings_drift import get_historical_earnings
    
    spy_close = spy_df["Close"].squeeze()
    
    for day_name, day_num in [("Monday", 0), ("Friday", 4)]:
        trades = []
        for ticker, df in all_data.items():
            earn = get_historical_earnings(ticker, lookback_days=700)
            if earn.empty:
                continue
            close = df["Close"]
            
            for _, row in earn.iterrows():
                if row["surprise_pct"] < 10:
                    continue
                
                edate = pd.Timestamp(row["date"])
                if edate.weekday() != day_num:
                    continue
                
                if edate.tzinfo:
                    edate = edate.tz_localize(None)
                
                idx_mask = close.index >= edate
                if idx_mask.sum() == 0:
                    continue
                entry_idx = close.index[idx_mask][0]
                entry_pos = close.index.get_loc(entry_idx) + 1
                if entry_pos >= len(close) - 40:
                    continue
                
                exit_pos = min(entry_pos + 40, len(close) - 1)
                entry_price = float(close.iloc[entry_pos])
                exit_price = float(close.iloc[exit_pos])
                stock_ret = (exit_price - entry_price) / entry_price
                
                spy_entry = spy_close.asof(close.index[entry_pos])
                spy_exit = spy_close.asof(close.index[exit_pos])
                spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
                
                trades.append({"alpha_pct": (stock_ret - spy_ret) * 100})
        
        if len(trades) >= 10:
            df = pd.DataFrame(trades)
            m = metrics_only(df)
            logger.info(
                f"  {day_name} earnings: n={m['signals']} med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
            )

def main():
    logger.info("=" * 70)
    logger.info("  FAST EDGE SEARCH")
    logger.info("=" * 70)
    
    logger.info("Loading data...")
    all_data = fetch_bulk(UNIVERSE, days=600)
    spy_df = fetch_spy(days=600)
    logger.info(f"Got {len(all_data)} tickers\n")
    
    # Run tests
    test_earnings_surprise_momentum(all_data, spy_df)
    short_result = test_shorting_large_misses(all_data, spy_df)
    test_different_hold_periods(all_data, spy_df)
    test_weekly_patterns(all_data, spy_df)
    
    logger.info("\n" + "=" * 70)
    if short_result:
        logger.info("PROFITABLE STRATEGY FOUND:")
        logger.info(f"  Strategy: {short_result['strategy']}")
        logger.info(f"  Params: {short_result['params']}")
        logger.info(f"  Median alpha: {short_result['metrics']['median_alpha']:.2f}%")
        logger.info(f"  Alpha hit rate: {short_result['metrics']['alpha_hit']:.1f}%")
    else:
        logger.info("No strong edges found in focused search.")
        logger.info("\nKey insight: Earnings drift with simple filters is marginal.")
        logger.info("Need different data sources or timeframes to find real alpha.")
    logger.info("=" * 70)

if __name__ == "__main__":
    sys.exit(main())
