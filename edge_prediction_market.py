#!/usr/bin/env python3
"""
Prediction Market Edge - Using Polymarket as contrarian filter
Hypothesis: When prediction markets are pessimistic but earnings beat,
the upside is larger (surprise against expectations).
"""
import logging
import sys
import pandas as pd
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Sample tickers that commonly have prediction markets
POLY_TICKERS = ["AAPL", "TSLA", "NVDA", "META", "GOOGL", "AMZN", "MSFT", "NFLX", "AMD", "COIN"]

def fetch_polymarket_sentiment(ticker: str) -> Optional[Dict]:
    """
    Check if there's a relevant Polymarket market for this ticker.
    Returns sentiment info if available.
    """
    try:
        from prediction_markets import get_earnings_beat_odds
        odds = get_earnings_beat_odds(ticker)
        if odds is not None:
            return {"odds": odds, "source": "polymarket"}
        return None
    except:
        return None

def backtest_with_pm_filter(
    all_data: Dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    min_surprise: float = 10.0,
    pm_threshold: float = 0.40,  # Prediction market < 40% = pessimistic
    entry_delay: int = 1,
    hold_days: int = 40,
) -> pd.DataFrame:
    """
    Only take trades when prediction markets are pessimistic (contrarian).
    """
    from earnings_drift import get_historical_earnings
    from prediction_markets import get_earnings_beat_odds
    
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for ticker, df in all_data.items():
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        
        close = df["Close"]
        
        for _, row in earn.iterrows():
            if row["surprise_pct"] < min_surprise:
                continue
            
            # Get prediction market odds for this earnings date
            # Note: In reality, we'd need to match specific earnings dates to market dates
            # For now, we check if current odds exist (approximation)
            pm_data = fetch_polymarket_sentiment(ticker)
            if not pm_data:
                continue
            
            odds = pm_data["odds"]
            
            # Only take trades when PM is pessimistic but we beat
            if odds >= pm_threshold:
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
            stock_ret = (exit_price - entry_price) / entry_price
            
            spy_entry = spy_close.asof(close.index[entry_pos])
            spy_exit = spy_close.asof(close.index[exit_pos])
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            results.append({
                "date": row["date"],
                "ticker": ticker,
                "surprise_pct": row["surprise_pct"],
                "pm_odds": odds,
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    return pd.DataFrame(results)

def find_high_short_unexpected_beat(all_data, spy_df):
    """
    High short interest + earnings beat = forced covering.
    Structural edge: shorts MUST cover.
    """
    logger.info("\n--- HIGH SHORT INTEREST + EARNINGS BEAT ---")
    
    from backtest import UNIVERSE, metrics_only, fetch_bulk, fetch_spy
    from earnings_drift import get_historical_earnings
    import yfinance as yf
    
    spy_close = spy_df["Close"].squeeze()
    results = []
    
    for ticker, df in all_data.items():
        # Get short interest
        try:
            tk = yf.Ticker(ticker)
            info = tk.info
            short_pct = info.get("shortPercentOfFloat", 0) * 100 if info.get("shortPercentOfFloat") else 0
        except:
            continue
        
        if short_pct < 15:  # Need high short interest
            continue
        
        earn = get_historical_earnings(ticker, lookback_days=700)
        if earn.empty:
            continue
        
        close = df["Close"]
        
        for _, row in earn.iterrows():
            if row["surprise_pct"] < 10:
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
            
            exit_pos = min(entry_pos + 20, len(close) - 1)
            entry_price = float(close.iloc[entry_pos])
            exit_price = float(close.iloc[exit_pos])
            stock_ret = (exit_price - entry_price) / entry_price
            
            spy_entry = spy_close.asof(close.index[entry_pos])
            spy_exit = spy_close.asof(close.index[exit_pos])
            spy_ret = (float(spy_exit) - float(spy_entry)) / float(spy_entry) if spy_entry and spy_exit else 0
            
            results.append({
                "date": row["date"],
                "ticker": ticker,
                "surprise_pct": row["surprise_pct"],
                "short_pct": short_pct,
                "stock_return_pct": round(stock_ret * 100, 2),
                "spy_return_pct": round(spy_ret * 100, 2),
                "alpha_pct": round((stock_ret - spy_ret) * 100, 2),
            })
    
    if len(results) >= 10:
        df = pd.DataFrame(results)
        m = metrics_only(df)
        logger.info(
            f"  High SI (15%+) + Beat | n={m['signals']} "
            f"med_alpha={m['median_alpha']:.2f}% hit={m['alpha_hit']:.1f}%"
        )
        return df, m
    return None, None

def main():
    logger.info("=" * 70)
    logger.info("  PREDICTION MARKET / STRUCTURAL EDGE SEARCH")
    logger.info("=" * 70)
    
    from backtest import fetch_bulk, fetch_spy, metrics_only
    
    # Focus on popular stocks where prediction markets exist
    logger.info("\nLoading data for popular tickers...")
    all_data = fetch_bulk(POLY_TICKERS, days=600)
    spy_df = fetch_spy(days=600)
    logger.info(f"Got {len(all_data)} tickers with prediction market potential\n")
    
    # 1. Try prediction market contrarian filter
    logger.info("--- POLYMARKET CONTRARIAN FILTER ---")
    logger.info("(Note: Requires active earnings markets on Polymarket)")
    
    # Check current markets
    try:
        from prediction_markets import fetch_tradeable_markets
        markets = fetch_tradeable_markets(active_only=True, limit=20, filter_relevant=True)
        stock_markets = [m for m in markets if any(t in m.get("title", "").upper() for t in POLY_TICKERS)]
        logger.info(f"Found {len(stock_markets)} stock-related prediction markets")
        for m in stock_markets[:3]:
            logger.info(f"  {m['yes_prob']:.0%} Yes | {m['title'][:50]}")
    except Exception as e:
        logger.info(f"Could not fetch prediction markets: {e}")
    
    # 2. High short interest + beat (structural edge)
    df, metrics = find_high_short_unexpected_beat(all_data, spy_df)
    
    # 3. Summary
    logger.info("\n" + "=" * 70)
    if df is not None and metrics:
        if metrics["median_alpha"] > 0.5 and metrics["alpha_hit"] > 52:
            logger.info("EDGE FOUND: High short interest + earnings beat")
            logger.info(f"  Median alpha: {metrics['median_alpha']:.2f}%")
            logger.info(f"  Alpha hit rate: {metrics['alpha_hit']:.1f}%")
            logger.info(f"  Structural reason: Shorts must cover on unexpected beat")
            logger.info("\nTop trades:")
            top = df.sort_values("alpha_pct", ascending=False).head(5)
            for _, row in top.iterrows():
                logger.info(f"  {row['date']} {row['ticker']}: {row['alpha_pct']:+.1f}% alpha, SI={row['short_pct']:.1f}%")
        else:
            logger.info("High short + beat showed promise but not strong enough:")
            logger.info(f"  Median alpha: {metrics['median_alpha']:.2f}%")
            logger.info(f"  Hit rate: {metrics['alpha_hit']:.1f}%")
    else:
        logger.info("No structural edge found in current data.")
        logger.info("\nKEY INSIGHT: Real alpha requires either:")
        logger.info("1. Proprietary data (options flow, institutional prints)")
        logger.info("2. Speed advantage (sub-second reaction)")
        logger.info("3. Structural forcing (mandated buying/selling)")
        logger.info("4. Behavioral edges (predictable retail patterns)")
    logger.info("=" * 70)

if __name__ == "__main__":
    sys.exit(main())
