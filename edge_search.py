#!/usr/bin/env python3
"""
Edge Search: Find real alpha through signal combinations and contrarian angles.
Tests intersections of multiple signals to find where the edge compounds.
"""
import logging
import sys
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest import (
    UNIVERSE, fetch_bulk, fetch_spy, backtest_earnings, metrics_only,
)

# Import all available signal modules
sys.path.insert(0, '/Users/home/stocks')

def load_volume_signals(tickers: List[str], all_data: Dict[str, pd.DataFrame]) -> Dict[str, dict]:
    """Pre-compute volume signals for all tickers at all dates."""
    from volume_anomaly import score_volume_at
    signals = {}
    for ticker, df in all_data.items():
        if df is None or len(df) < 60:
            continue
        ticker_signals = {}
        for i in range(60, len(df)):
            vs = score_volume_at(df, i)
            if vs and vs["signal"] != "NONE":
                date = df.index[i].strftime("%Y-%m-%d")
                ticker_signals[date] = vs
        signals[ticker] = ticker_signals
    return signals

def load_squeeze_signals(tickers: List[str], all_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, dict]]:
    """Pre-compute squeeze signals."""
    from squeeze_detector import analyze_squeeze, DEFAULT_CONFIG
    signals = {}
    cfg = DEFAULT_CONFIG
    for ticker, df in all_data.items():
        if df is None or len(df) < 20:
            continue
        ticker_signals = {}
        try:
            sq = analyze_squeeze(ticker, cfg)
            if sq and sq.signal in ["SQUEEZE_SETUP", "WATCH"]:
                # Use current date for squeeze signal
                date = df.index[-1].strftime("%Y-%m-%d")
                ticker_signals[date] = {
                    "short_interest": sq.short_pct_float,
                    "days_to_cover": sq.days_to_cover,
                    "signal": sq.signal,
                }
        except:
            pass
        signals[ticker] = ticker_signals
    return signals

def combined_backtest(
    all_data: Dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    volume_signals: Dict[str, Dict[str, dict]],
    squeeze_signals: Dict[str, Dict[str, dict]],
    require_volume: bool = False,
    require_squeeze: bool = False,
    require_high_short: bool = False,
    min_short_interest: float = 10.0,
    entry_delay: int = 1,
    hold_days: int = 40,
    min_surprise: float = 10.0,
    max_surprise: float = 100.0,
    only_direction: str = "BUY",
) -> pd.DataFrame:
    """Backtest earnings with optional volume/squeeze filters."""
    from earnings_drift import get_historical_earnings
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        
        close = df["Close"]
        vol_sig = volume_signals.get(ticker, {})
        sq_sig = squeeze_signals.get(ticker, {})
        
        for _, row in earn.iterrows():
            if abs(row["surprise_pct"]) < min_surprise:
                continue
            if row["surprise_pct"] > max_surprise:
                continue
                
            direction = "BUY" if row["surprise_pct"] > 0 else "SHORT"
            if only_direction and direction != only_direction:
                continue
            
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            
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
            
            entry_date = close.index[entry_pos]
            entry_date_str = entry_date.strftime("%Y-%m-%d")
            
            # Check volume filter
            if require_volume:
                if entry_date_str not in vol_sig:
                    continue
                vs = vol_sig[entry_date_str]
                if vs["signal"] not in ["ACCUMULATION", "SPIKE_BUY"]:
                    continue
            
            # Check squeeze/high short filter
            if require_squeeze or require_high_short:
                # Check if we have short interest data around entry date
                sq = sq_sig.get(entry_date_str) or sq_sig.get(df.index[entry_pos - 1].strftime("%Y-%m-%d"))
                if not sq:
                    continue
                if require_high_short and sq.get("short_interest", 0) < min_short_interest:
                    continue
                if require_squeeze and sq.get("signal") not in ["SHORT_SQUEEZE", "SQUEEZE_RISK"]:
                    continue
            
            entry_price = float(close.iloc[entry_pos])
            exit_price = float(close.iloc[exit_pos])
            stock_ret = (exit_price - entry_price) / entry_price
            if direction == "SHORT":
                stock_ret = -stock_ret
            
            spy_entry = spy_close.asof(entry_date)
            spy_exit = spy_close.asof(close.index[exit_pos])
            if pd.isna(spy_entry) or pd.isna(spy_exit) or float(spy_entry) == 0:
                spy_ret = 0.0
            else:
                spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry)
            
            results.append({
                "date": edate.strftime("%Y-%m-%d"),
                "ticker": ticker,
                "direction": direction,
                "surprise_pct": round(row["surprise_pct"], 1),
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    return pd.DataFrame(results)

def search_edges():
    """Search for profitable edge combinations."""
    logger.info("=" * 70)
    logger.info("  EDGE SEARCH: Finding Real Alpha")
    logger.info("=" * 70)
    
    logger.info("\nLoading data...")
    all_data = fetch_bulk(UNIVERSE, days=600)
    spy_df = fetch_spy(days=600)
    logger.info(f"Got {len(all_data)} tickers")
    
    logger.info("\nPre-computing volume signals...")
    volume_signals = load_volume_signals(UNIVERSE, all_data)
    
    logger.info("Pre-computing squeeze signals...")
    squeeze_signals = load_squeeze_signals(UNIVERSE, all_data)
    
    logger.info("\n" + "=" * 70)
    logger.info("  Testing combinations...")
    logger.info("=" * 70)
    
    best = None
    best_metrics = None
    best_params = None
    
    # Search through parameter combinations
    for hold_days in [20, 40]:
        for min_surprise in [10, 15, 20, 30]:
            for require_volume in [False, True]:
                for require_high_short in [False, True]:
                    for require_squeeze in [False] if require_high_short else [False, True]:
                        # Skip impossible combinations
                        if require_squeeze and not require_high_short:
                            continue
                        
                        df = combined_backtest(
                            all_data, spy_df, volume_signals, squeeze_signals,
                            require_volume=require_volume,
                            require_squeeze=require_squeeze,
                            require_high_short=require_high_short,
                            entry_delay=1,
                            hold_days=hold_days,
                            min_surprise=min_surprise,
                        )
                        
                        if len(df) < 10:
                            continue
                        
                        m = metrics_only(df)
                        
                        # Higher bar for "profitable"
                        is_good = m["median_alpha"] > 1.0 and m["alpha_hit"] > 52
                        is_great = m["median_alpha"] > 2.0 and m["alpha_hit"] > 55
                        
                        if is_good or is_great:
                            status = "GREAT" if is_great else "GOOD"
                            vol_str = "+VOL" if require_volume else ""
                            short_str = f"+SHORT>{min_surprise}%" if require_high_short else ""
                            logger.info(
                                f"  {status}: hold={hold_days}d surprise>={min_surprise}% "
                                f"{vol_str}{short_str} | n={m['signals']} "
                                f"med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
                            )
                            
                            if is_great and (best_metrics is None or m["median_alpha"] > best_metrics["median_alpha"]):
                                best = df
                                best_metrics = m
                                best_params = {
                                    "hold_days": hold_days,
                                    "min_surprise": min_surprise,
                                    "require_volume": require_volume,
                                    "require_high_short": require_high_short,
                                    "require_squeeze": require_squeeze,
                                }
    
    logger.info("\n" + "=" * 70)
    if best is not None:
        logger.info("BEST EDGE FOUND:")
        logger.info(f"  Params: {best_params}")
        logger.info(f"  Signals: {best_metrics['signals']}")
        logger.info(f"  Median alpha: {best_metrics['median_alpha']:.2f}%")
        logger.info(f"  Alpha hit rate: {best_metrics['alpha_hit']:.1f}%")
        logger.info(f"  Avg alpha: {best_metrics['avg_alpha']:.2f}%")
        logger.info("\nTop 10 trades:")
        best_sorted = best.sort_values("alpha_pct", ascending=False)
        for _, row in best_sorted.head(10).iterrows():
            logger.info(f"  {row['date']} {row['ticker']}: alpha={row['alpha_pct']:+.1f}% surprise={row['surprise_pct']:.1f}%")
        return best_params, best_metrics
    else:
        logger.info("No edge meeting higher bar found in standard combinations.")
        logger.info("\nTrying contrarian approaches...")
        return None, None

def search_contrarian_edges(all_data, spy_df, volume_signals, squeeze_signals):
    """Try contrarian approaches - fading retail, fading prediction markets."""
    logger.info("\n" + "=" * 70)
    logger.info("  CONTRARIAN EDGE SEARCH")
    logger.info("=" * 70)
    
    # Approach 1: Short large misses after initial drop
    logger.info("\n1. Shorting large misses with delayed entry...")
    results = []
    from earnings_drift import get_historical_earnings
    spy_close = spy_df["Close"].squeeze()
    
    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        close = df["Close"]
        
        for _, row in earn.iterrows():
            if row["surprise_pct"] > -15:  # Large miss only
                continue
            
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            
            idx_mask = close.index >= edate
            if idx_mask.sum() == 0:
                continue
            
            entry_idx = close.index[idx_mask][0]
            # Enter 2-3 days after (fade the bounce)
            for delay in [2, 3]:
                entry_pos = close.index.get_loc(entry_idx) + delay
                if entry_pos >= len(close) - 20:
                    continue
                
                exit_pos = min(entry_pos + 20, len(close) - 1)
                entry_price = float(close.iloc[entry_pos])
                exit_price = float(close.iloc[exit_pos])
                
                # Short the stock
                stock_ret = -((exit_price - entry_price) / entry_price)
                
                spy_entry = spy_close.asof(close.index[entry_pos])
                spy_exit = spy_close.asof(close.index[exit_pos])
                spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
                
                results.append({
                    "ticker": ticker,
                    "delay": delay,
                    "stock_return_pct": stock_ret * 100,
                    "spy_return_pct": spy_ret * 100,
                    "alpha_pct": (stock_ret - spy_ret) * 100,
                })
    
    if results:
        df = pd.DataFrame(results)
        m = metrics_only(df)
        logger.info(f"   Short large misses, fade bounce: n={m['signals']} med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%")
        
        if m["median_alpha"] > 1 and m["alpha_hit"] > 52:
            logger.info("   -> PROFITABLE CONTRARIAN SHORT STRATEGY FOUND")
            return {"strategy": "fade_large_misses", "delay": "2-3d"}, m
    
    # Approach 2: Buy large beats with low retail sentiment
    logger.info("\n2. Large beats with contrarian retail positioning...")
    # This would require historical sentiment data - simplified version:
    # Buy very large beats (>40%) with volume spike (institutional, not retail)
    
    results = []
    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        close = df["Close"]
        vol_sig = volume_signals.get(ticker, {})
        
        for _, row in earn.iterrows():
            if row["surprise_pct"] < 40:  # Very large beat only
                continue
            
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            
            idx_mask = close.index >= edate
            if idx_mask.sum() == 0:
                continue
            
            entry_idx = close.index[idx_mask][0]
            entry_pos = close.index.get_loc(entry_idx) + 1
            if entry_pos >= len(close) - 20:
                continue
            
            # Check for volume spike (institutional accumulation)
            entry_date = close.index[entry_pos].strftime("%Y-%m-%d")
            if entry_date not in vol_sig:
                continue
            vs = vol_sig[entry_date]
            if vs["signal"] not in ["ACCUMULATION", "SPIKE_BUY"]:
                continue
            
            exit_pos = min(entry_pos + 20, len(close) - 1)
            entry_price = float(close.iloc[entry_pos])
            exit_price = float(close.iloc[exit_pos])
            stock_ret = (exit_price - entry_price) / entry_price
            
            spy_entry = spy_close.asof(close.index[entry_pos])
            spy_exit = spy_close.asof(close.index[exit_pos])
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            results.append({
                "ticker": ticker,
                "stock_return_pct": stock_ret * 100,
                "spy_return_pct": spy_ret * 100,
                "alpha_pct": (stock_ret - spy_ret) * 100,
            })
    
    if results:
        df = pd.DataFrame(results)
        m = metrics_only(df)
        logger.info(f"   Large beats + volume spike: n={m['signals']} med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%")
        
        if m["median_alpha"] > 2 and m["alpha_hit"] > 55:
            logger.info("   -> PROFITABLE CONTRARIAN LONG STRATEGY FOUND")
            return {"strategy": "large_beats_with_volume", "min_surprise": 40}, m
    
    return None, None

def main():
    logger.info("Starting edge search...")
    
    all_data = fetch_bulk(UNIVERSE, days=600)
    spy_df = fetch_spy(days=600)
    volume_signals = load_volume_signals(UNIVERSE, all_data)
    squeeze_signals = load_squeeze_signals(UNIVERSE, all_data)
    
    params, metrics = search_edges()
    
    if params is None:
        params, metrics = search_contrarian_edges(all_data, spy_df, volume_signals, squeeze_signals)
    
    if params and metrics:
        logger.info("\n" + "=" * 70)
        logger.info("REAL EDGE FOUND - SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Strategy: {params}")
        logger.info(f"Backtest signals: {metrics['signals']}")
        logger.info(f"Median alpha: {metrics['median_alpha']:.2f}% per trade")
        logger.info(f"Alpha hit rate: {metrics['alpha_hit']:.1f}%")
        logger.info(f"Average alpha: {metrics['avg_alpha']:.2f}%")
        return 0
    else:
        logger.info("\n" + "=" * 70)
        logger.info("No strong edge found in current search space.")
        logger.info("Recommendations:")
        logger.info("1. Expand universe beyond growth stocks (try value, international)")
        logger.info("2. Use intraday data for better entry timing")
        logger.info("3. Add options data (implied vs realized vol)")
        logger.info("4. Consider macro regime filters (only trade in certain Fed cycles)")
        logger.info("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
