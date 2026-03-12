#!/usr/bin/env python3
"""
Alternative Edge Search - Different angles on earnings
1. Consecutive beats (earnings momentum)
2. Pre-earnings run-up (enter before, sell on announcement)
3. Post-earnings mean reversion (fade large moves)
"""
import logging
import sys
import pandas as pd
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest import UNIVERSE, fetch_bulk, fetch_spy, metrics_only

def get_consecutive_beats(ticker: str, min_consecutive: int = 2) -> List[Tuple[str, float, float]]:
    """
    Find stocks with consecutive earnings beats.
    Returns list of (date, surprise_pct, cumulative_surprise) for each qualifying earnings.
    """
    from earnings_drift import get_historical_earnings
    earn = get_historical_earnings(ticker, lookback_days=700)
    if earn.empty:
        return []
    
    # Sort by date ascending
    earn = earn.sort_values("date")
    
    results = []
    consecutive_count = 0
    cumulative_surprise = 0
    
    for _, row in earn.iterrows():
        surprise = row["surprise_pct"]
        if surprise > 0:  # Beat
            consecutive_count += 1
            cumulative_surprise += surprise
        else:  # Miss
            consecutive_count = 0
            cumulative_surprise = 0
        
        if consecutive_count >= min_consecutive:
            results.append((row["date"], surprise, cumulative_surprise))
    
    return results

def backtest_consecutive_beats(
    all_data: Dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    min_consecutive: int = 2,
    hold_days: int = 40,
    entry_delay: int = 1
) -> pd.DataFrame:
    """Backtest buying after consecutive beats."""
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for ticker, df in all_data.items():
        beats = get_consecutive_beats(ticker, min_consecutive)
        if not beats:
            continue
        
        close = df["Close"]
        
        for date_str, surprise, cumulative in beats:
            edate = pd.Timestamp(date_str)
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
            stock_ret = (exit_price - entry_price) / entry_price
            
            spy_entry = spy_close.asof(close.index[entry_pos])
            spy_exit = spy_close.asof(close.index[exit_pos])
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            results.append({
                "date": date_str,
                "ticker": ticker,
                "surprise_pct": surprise,
                "cumulative_surprise": cumulative,
                "consecutive": min_consecutive,
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    return pd.DataFrame(results)

def backtest_pre_earnings(
    all_data: Dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    days_before: int = 5,
    hold_days: int = 1,  # Sell on earnings day
    min_surprise: float = 15.0
) -> pd.DataFrame:
    """
    Backtest buying before earnings and selling on the announcement day.
    Hypothesis: Pre-earnings run-up exists, especially for expected beats.
    """
    from earnings_drift import get_historical_earnings
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
            
            # Find entry date (days_before days before earnings)
            idx_mask = close.index < edate
            if idx_mask.sum() == 0:
                continue
            eligible = close.index[idx_mask]
            if len(eligible) < days_before:
                continue
            entry_date = eligible[-days_before]
            entry_pos = close.index.get_loc(entry_date)
            
            # Exit on earnings date
            exit_candidates = close.index[close.index >= edate]
            if len(exit_candidates) == 0:
                continue
            exit_date = exit_candidates[0]
            exit_pos = close.index.get_loc(exit_date)
            
            if exit_pos <= entry_pos:
                continue
            
            entry_price = float(close.iloc[entry_pos])
            exit_price = float(close.iloc[exit_pos])
            stock_ret = (exit_price - entry_price) / entry_price
            
            spy_entry = spy_close.asof(entry_date)
            spy_exit = spy_close.asof(exit_date)
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            direction = "BUY" if row["surprise_pct"] > 0 else "SHORT"
            if direction == "SHORT":
                stock_ret = -stock_ret
            
            results.append({
                "date": edate.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "direction": direction,
                "surprise_pct": row["surprise_pct"],
                "days_before": days_before,
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    return pd.DataFrame(results)

def backtest_fade_large_moves(
    all_data: Dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    move_threshold: float = 10.0,  # Price move % threshold
    hold_days: int = 5,
) -> pd.DataFrame:
    """
    Backtest fading large earnings moves (mean reversion).
    Hypothesis: Large moves overreact and partially reverse.
    """
    from earnings_drift import get_historical_earnings
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        close = df["Close"]
        
        for _, row in earn.iterrows():
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            
            idx_mask = close.index >= edate
            if idx_mask.sum() < 3:
                continue
            
            earn_idx = close.index[idx_mask][0]
            earn_pos = close.index.get_loc(earn_idx)
            if earn_pos < 1:
                continue
            
            # Calculate day-of/after move
            pre_price = float(close.iloc[earn_pos - 1])
            post_price = float(close.iloc[min(earn_pos + 1, len(close) - 1)])
            move_pct = abs((post_price - pre_price) / pre_price * 100)
            
            if move_pct < move_threshold:
                continue
            
            # Fade the move - enter 1 day after, opposite direction
            entry_pos = earn_pos + 2
            if entry_pos >= len(close) - hold_days:
                continue
            
            entry_price = float(close.iloc[entry_pos])
            exit_pos = min(entry_pos + hold_days, len(close) - 1)
            exit_price = float(close.iloc[exit_pos])
            
            # Fade = opposite of initial move
            fade_up = post_price < pre_price  # If it dropped, we go long (fade)
            if fade_up:
                stock_ret = (exit_price - entry_price) / entry_price
            else:
                stock_ret = -(exit_price - entry_price) / entry_price  # Short
            
            spy_entry = spy_close.asof(close.index[entry_pos])
            spy_exit = spy_close.asof(close.index[exit_pos])
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            results.append({
                "date": edate.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "move_pct": round(move_pct, 1),
                "fade_direction": "LONG" if fade_up else "SHORT",
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    return pd.DataFrame(results)

def main():
    logger.info("=" * 70)
    logger.info("  ALTERNATIVE EDGE SEARCH")
    logger.info("  Testing: consecutive beats, pre-earnings, fade large moves")
    logger.info("=" * 70)
    
    logger.info("\nLoading data...")
    all_data = fetch_bulk(UNIVERSE[:50], days=600)  # Smaller universe for speed
    spy_df = fetch_spy(days=600)
    logger.info(f"Got {len(all_data)} tickers\n")
    
    best = None
    best_desc = None
    
    # 1. Consecutive beats
    logger.info("--- HYPOTHESIS: Consecutive earnings momentum ---")
    for consecutive in [2, 3]:
        df = backtest_consecutive_beats(all_data, spy_df, min_consecutive=consecutive, hold_days=40)
        if len(df) < 10:
            continue
        m = metrics_only(df)
        logger.info(
            f"  {consecutive}+ consecutive beats | n={m['signals']} "
            f"med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
        )
        if m["median_alpha"] > 0.5 and m["alpha_hit"] > 52:
            if best is None or m["median_alpha"] > best["median_alpha"]:
                best = m
                best_desc = f"Consecutive beats ({consecutive}+)"
    
    # 2. Pre-earnings run-up
    logger.info("\n--- HYPOTHESIS: Pre-earnings run-up ---")
    for days_before in [3, 5, 7]:
        for min_surprise in [15, 20, 30]:
            df = backtest_pre_earnings(all_data, spy_df, days_before=days_before, min_surprise=min_surprise)
            buys = df[df["direction"] == "BUY"] if "direction" in df.columns else df
            if len(buys) < 10:
                continue
            m = metrics_only(buys)
            if m["median_alpha"] > 0.5 and m["alpha_hit"] > 52:
                logger.info(
                    f"  {days_before}d before earnings, surprise>={min_surprise}% | n={m['signals']} "
                    f"med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
                )
                if best is None or m["median_alpha"] > best["median_alpha"]:
                    best = m
                    best_desc = f"Pre-earnings ({days_before}d before, surprise>={min_surprise}%)"
    
    # 3. Fade large moves
    logger.info("\n--- HYPOTHESIS: Fade large earnings moves (mean reversion) ---")
    for threshold in [10, 15, 20]:
        for hold_days in [3, 5, 10]:
            df = backtest_fade_large_moves(all_data, spy_df, move_threshold=threshold, hold_days=hold_days)
            if len(df) < 10:
                continue
            m = metrics_only(df)
            if m["median_alpha"] > 1.0 and m["alpha_hit"] > 55:
                logger.info(
                    f"  Fade >{threshold}% move, hold {hold_days}d | n={m['signals']} "
                    f"med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
                )
                if best is None or m["median_alpha"] > best["median_alpha"]:
                    best = m
                    best_desc = f"Fade large moves (>{threshold}%, hold {hold_days}d)"
    
    logger.info("\n" + "=" * 70)
    if best:
        logger.info("BEST EDGE FOUND:")
        logger.info(f"  Strategy: {best_desc}")
        logger.info(f"  Median alpha: {best['median_alpha']:.2f}%")
        logger.info(f"  Alpha hit rate: {best['alpha_hit']:.1f}%")
        logger.info(f"  Signals: {best['signals']}")
    else:
        logger.info("No strong alternative edges found.")
        logger.info("\nPERSISTENT ISSUE: Standard earnings signals are marginal.")
        logger.info("Need non-standard data: options flow, institutional positioning,")
        logger.info("or intraday patterns to find real alpha.")
    logger.info("=" * 70)

if __name__ == "__main__":
    sys.exit(main())
