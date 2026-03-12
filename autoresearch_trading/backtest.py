#!/usr/bin/env python3
"""
AUTORESEARCH TRADING - BACKTEST ENGINE
=====================================
Evaluates trading strategies with metrics.
Run: python backtest.py
"""
import logging
import sys
from datetime import datetime
from typing import List, Dict
import pandas as pd
import numpy as np
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Top liquid stocks for testing (smaller to avoid rate limits)
TEST_UNIVERSE = [
    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA"
]

def fetch_intraday_data(ticker: str, period: str = "120d", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data from yfinance."""
    import time
    time.sleep(0.5)  # Rate limit protection
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval, auto_adjust=True)
        if df.empty or len(df) < 30:
            return None
        
        # Standardize column names (yfinance returns Title Case)
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        
        # Remove timezone
        if hasattr(df.index, "tz") and df.index.tz:
            df.index = df.index.tz_localize(None)
        
        return df
    except Exception as e:
        logger.debug(f"Failed to fetch {ticker}: {e}")
        return None

def calculate_metrics(trades: List, equity_df: pd.DataFrame) -> Dict:
    """Calculate backtest performance metrics."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "avg_return": 0,
            "sharpe": 0,
            "max_drawdown": 0,
            "avg_trade_duration": 0
        }
    
    profits = [t.pnl_pct for t in trades if t.pnl_pct > 0]
    losses = [abs(t.pnl_pct) for t in trades if t.pnl_pct <= 0]
    
    total_trades = len(trades)
    winning_trades = len(profits)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    gross_profit = sum(profits)
    gross_loss = sum(losses)
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    
    avg_return = np.mean([t.pnl_pct for t in trades])
    
    # Calculate trade durations
    durations = []
    for t in trades:
        try:
            duration = (t.exit_date - t.entry_date).total_seconds() / 3600  # hours
            durations.append(duration)
        except:
            pass
    avg_duration = np.mean(durations) if durations else 0
    avg_duration_days = avg_duration / 24  # Convert to days
    
    # Estimate Sharpe (simplified - using returns)
    returns = [t.pnl_pct for t in trades]
    sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    # Estimate max drawdown from trades (simplified)
    cumulative = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = cumulative - running_max
    max_drawdown = abs(min(drawdown, default=0))
    
    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "avg_return": round(avg_return, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(max_drawdown, 2),
        "avg_trade_duration_hours": round(avg_duration, 1),
        "avg_trade_duration_days": round(avg_duration_days, 2)
    }

def run_backtest(strategy_config: dict, tickers: List[str] = None, verbose: bool = True) -> Dict:
    """Run backtest across universe and return metrics."""
    from strategy import backtest_strategy
    
    tickers = tickers or TEST_UNIVERSE
    all_trades = []
    
    if verbose:
        logger.info(f"\nRunning backtest on {len(tickers)} tickers...")
        logger.info(f"Strategy: {strategy_config['INDICATOR_1']} + {strategy_config['INDICATOR_2']}")
    
    for ticker in tickers:
        # Use daily data to avoid rate limits
        df = fetch_intraday_data(ticker, period="120d", interval="1d")
        if df is None or len(df) < 30:
            if verbose:
                logger.info(f"  Skipping {ticker} (no data)")
            continue
        
        trades, equity = backtest_strategy(df, strategy_config)
        if verbose and trades:
            logger.info(f"  {ticker}: {len(trades)} trades")
        all_trades.extend(trades)
    
    metrics = calculate_metrics(all_trades, None)
    
    if verbose:
        logger.info(f"\nResults:")
        logger.info(f"  Total trades: {metrics['total_trades']}")
        logger.info(f"  Win rate: {metrics['win_rate']}%")
        logger.info(f"  Profit factor: {metrics['profit_factor']}")
        logger.info(f"  Avg return/trade: {metrics['avg_return']}%")
        logger.info(f"  Sharpe ratio: {metrics.get('sharpe', 0)}")
        logger.info(f"  Max drawdown: {metrics.get('max_drawdown', 0)}%")
        logger.info(f"  Avg duration: {metrics.get('avg_trade_duration_hours', 0)}h")
        
        # Show recent trades
        if all_trades:
            logger.info(f"\nLast 5 trades:")
            for t in all_trades[-5:]:
                logger.info(f"  {t.ticker} {t.position}: {t.pnl_pct:+.2f}% ({t.exit_reason})")
    
    return metrics, all_trades

def score_strategy(metrics: Dict) -> float:
    """Score strategy for autoresearch comparison."""
    # Weighted scoring
    score = 0
    
    # Win rate (most important)
    if metrics["win_rate"] > 55:
        score += 40
    elif metrics["win_rate"] > 50:
        score += 20
    
    # Profit factor
    if metrics["profit_factor"] > 1.5:
        score += 30
    elif metrics["profit_factor"] > 1.3:
        score += 15
    elif metrics["profit_factor"] > 1.0:
        score += 5
    
    # Sharpe
    if metrics["sharpe"] > 1.0:
        score += 20
    elif metrics["sharpe"] > 0.5:
        score += 10
    
    # Drawdown penalty
    if metrics["max_drawdown"] < 10:
        score += 10
    elif metrics["max_drawdown"] > 20:
        score -= 20
    
    # Trade count penalty (need enough samples)
    if metrics["total_trades"] < 20:
        score -= 30
    
    return score

def main():
    logger.info("=" * 70)
    logger.info("  AUTORESEARCH TRADING - BACKTEST ENGINE")
    logger.info("=" * 70)
    
    # Import current strategy config
    from strategy import STRATEGY_CONFIG
    
    # Run backtest
    metrics, trades = run_backtest(STRATEGY_CONFIG, verbose=True)
    
    # Score
    score = score_strategy(metrics)
    logger.info(f"\nStrategy Score: {score}/100")
    
    # Verdict
    logger.info("\n" + "=" * 70)
    if score >= 80:
        logger.info("VERDICT: KEEP - Strong strategy found!")
    elif score >= 50:
        logger.info("VERDICT: ITERATE - Promising but needs refinement")
    else:
        logger.info("VERDICT: REVERT - Poor performance, try different approach")
    logger.info("=" * 70)
    
    return score

if __name__ == "__main__":
    score = main()
    sys.exit(0 if score >= 50 else 1)
