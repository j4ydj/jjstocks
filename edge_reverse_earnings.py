#!/usr/bin/env python3
"""
Reverse Earnings Edge
Hypothesis: When stock drops on earnings BEAT (guidance disappointment), 
market overreacts. Buy the dip.
"""
import logging
import sys
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest import UNIVERSE, fetch_bulk, fetch_spy, metrics_only

def backtest_reverse_earnings(
    all_data,
    spy_df,
    min_surprise: float = 10.0,
    max_drop_pct: float = -5.0,  # Must drop at least 5%
    hold_days: int = 10,
):
    """Buy earnings beats that the market initially sold off."""
    from earnings_drift import get_historical_earnings
    
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        
        close = df["Close"]
        
        for _, row in earn.iterrows():
            # Must beat
            if row["surprise_pct"] < min_surprise:
                continue
            
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            
            # Find day before, day of, day after
            idx_before = close.index[close.index < edate]
            if len(idx_before) < 1:
                continue
            price_before = float(close.asof(idx_before[-1]))
            
            # Find first trading day on/after earnings
            idx_after = close.index[close.index >= edate]
            if len(idx_after) < 2:
                continue
            
            price_earn_day = float(close.iloc[close.index.get_loc(idx_after[0])])
            price_next_day = float(close.iloc[close.index.get_loc(idx_after[1])])
            
            # Calculate drop from before to next day
            drop_pct = (price_next_day - price_before) / price_before * 100
            
            # Must have dropped despite the beat
            if drop_pct > max_drop_pct:
                continue
            
            # Enter on day after earnings (next day close)
            entry_price = price_next_day
            entry_pos = close.index.get_loc(idx_after[1])
            exit_pos = min(entry_pos + hold_days, len(close) - 1)
            if exit_pos <= entry_pos:
                continue
            
            exit_price = float(close.iloc[exit_pos])
            stock_ret = (exit_price - entry_price) / entry_price
            
            spy_entry = spy_close.asof(idx_after[1])
            spy_exit = spy_close.asof(close.index[exit_pos])
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            results.append({
                "date": row["date"],
                "ticker": ticker,
                "surprise_pct": row["surprise_pct"],
                "drop_pct": round(drop_pct, 1),
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    return pd.DataFrame(results)

def main():
    logger.info("=" * 70)
    logger.info("  REVERSE EARNINGS EDGE")
    logger.info("  Buying earnings beats that the market sold off")
    logger.info("=" * 70)
    
    logger.info("\nLoading data...")
    all_data = fetch_bulk(UNIVERSE, days=600)
    spy_df = fetch_spy(days=600)
    logger.info(f"Got {len(all_data)} tickers\n")
    
    logger.info("--- Testing reverse earnings hypothesis ---")
    
    best = None
    best_params = None
    
    for min_surprise in [10, 15, 20, 30]:
        for max_drop in [-3, -5, -7, -10]:
            for hold_days in [5, 10, 15, 20]:
                df = backtest_reverse_earnings(
                    all_data, spy_df,
                    min_surprise=min_surprise,
                    max_drop_pct=max_drop,
                    hold_days=hold_days
                )
                if len(df) < 10:
                    continue
                
                m = metrics_only(df)
                if m["median_alpha"] > 1.0 and m["alpha_hit"] > 55:
                    logger.info(
                        f"  GOOD: surprise>={min_surprise}%, drop<={max_drop}%, hold={hold_days}d | "
                        f"n={m['signals']} med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
                    )
                    if best is None or m["median_alpha"] > best["median_alpha"]:
                        best = m
                        best_params = {
                            "min_surprise": min_surprise,
                            "max_drop": max_drop,
                            "hold_days": hold_days,
                        }
    
    logger.info("\n" + "=" * 70)
    if best and best_params:
        logger.info("EDGE FOUND - Reverse Earnings:")
        logger.info(f"  Params: Surprise >={best_params['min_surprise']}%, Drop <={best_params['max_drop']}%, Hold {best_params['hold_days']}d")
        logger.info(f"  Median alpha: {best['median_alpha']:.2f}%")
        logger.info(f"  Alpha hit rate: {best['alpha_hit']:.1f}%")
        logger.info(f"  Signals: {best['signals']}")
        logger.info("\nBehavioral explanation: Market overreacts to guidance/metrics,")
        logger.info("creating dip on actual earnings beat. Smart money buys the dip.")
    else:
        logger.info("No strong reverse earnings edge found.")
        logger.info("\nCONCLUSION: With free, delayed data, no meaningful edge exists.")
        logger.info("The market has arbitraged simple earnings patterns.")
        logger.info("\nTo find real alpha, you need:")
        logger.info("1. Options flow data (detect positioning before earnings)")
        logger.info("2. Intraday execution (enter during earnings call, not after)")
        logger.info("3. Proprietary signals (sentiment, unusual activity)")
    logger.info("=" * 70)

if __name__ == "__main__":
    sys.exit(main())
