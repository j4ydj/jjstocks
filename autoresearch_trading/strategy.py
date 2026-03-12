"""
TRADING STRATEGY - AUTORESEARCH VERSION
=======================================
This file is modified by the AI agent during experiments.
Baseline: Simple EMA crossover strategy.

Modify the parameters below to test different strategies.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# ============================================================================
# STRATEGY CONFIGURATION - MODIFY THESE PARAMETERS
# ============================================================================

STRATEGY_CONFIG = {
    # Timeframe - daily is more reliable for free data
    "TIMEFRAME": "1d",           # 1d (intraday often rate-limited)
    
    # Primary Indicator
    "INDICATOR_1": "EMA_CROSS",  # Options: EMA_CROSS, RSI, MACD, BBANDS, VOLUME
    "EMA_FAST": 10,
    "EMA_SLOW": 30,
    
    # Secondary Filter (optional)
    "INDICATOR_2": "NONE",       # Options: RSI, VOLUME, ATR, NONE
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70,
    "RSI_OVERSOLD": 30,
    
    # Risk Management
    "STOP_LOSS_PCT": 5.0,        # Stop loss percentage (wider for daily)
    "TAKE_PROFIT_PCT": 10.0,     # Take profit (0 = use indicator exit)
    
    # Position Sizing
    "POSITION_SIZE": 100,        # Dollar amount per trade
}

# ============================================================================
# STRATEGY LOGIC - MODIFY THESE FUNCTIONS
# ============================================================================

def calculate_indicators(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Calculate technical indicators.
    Add or modify indicators here.
    """
    df = df.copy()
    
    # EMA Crossover
    if config["INDICATOR_1"] == "EMA_CROSS":
        df["ema_fast"] = df["close"].ewm(span=config["EMA_FAST"]).mean()
        df["ema_slow"] = df["close"].ewm(span=config["EMA_SLOW"]).mean()
    
    # RSI
    if config["INDICATOR_2"] == "RSI" or config["INDICATOR_1"] == "RSI":
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=config["RSI_PERIOD"]).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=config["RSI_PERIOD"]).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
    
    # MACD
    if config["INDICATOR_1"] == "MACD" or config["INDICATOR_2"] == "MACD":
        ema_12 = df["close"].ewm(span=12).mean()
        ema_26 = df["close"].ewm(span=26).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
    
    # Bollinger Bands
    if config["INDICATOR_1"] == "BBANDS" or config["INDICATOR_2"] == "BBANDS":
        df["sma_20"] = df["close"].rolling(window=20).mean()
        std = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["sma_20"] + (std * 2)
        df["bb_lower"] = df["sma_20"] - (std * 2)
    
    # Volume
    if config["INDICATOR_2"] == "VOLUME":
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
    
    # ATR (Average True Range)
    if config["INDICATOR_2"] == "ATR":
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df["atr"] = true_range.rolling(14).mean()
    
    return df

def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Generate buy/sell signals based on indicators.
    Modify logic here to test different entry/exit rules.
    """
    df = df.copy()
    df["signal"] = 0  # 0 = hold, 1 = buy, -1 = sell
    
    # EMA Crossover signals
    if config["INDICATOR_1"] == "EMA_CROSS":
        df["signal"] = np.where(
            df["ema_fast"] > df["ema_slow"], 1, -1
        )
        # Only trade on crossovers
        df["position"] = df["signal"].diff()
    
    # RSI Mean Reversion
    elif config["INDICATOR_1"] == "RSI":
        df["signal"] = 0
        df.loc[df["rsi"] < config["RSI_OVERSOLD"], "signal"] = 1   # Buy oversold
        df.loc[df["rsi"] > config["RSI_OVERBOUGHT"], "signal"] = -1  # Sell overbought
        df["position"] = df["signal"]
    
    # MACD Momentum
    elif config["INDICATOR_1"] == "MACD":
        df["signal"] = np.where(df["macd"] > df["macd_signal"], 1, -1)
        df["position"] = df["signal"].diff()
    
    # Bollinger Bands Mean Reversion
    elif config["INDICATOR_1"] == "BBANDS":
        df["signal"] = 0
        df.loc[df["close"] < df["bb_lower"], "signal"] = 1   # Buy below lower band
        df.loc[df["close"] > df["bb_upper"], "signal"] = -1  # Sell above upper band
        df["position"] = df["signal"]
    
    # Add secondary filters
    if config["INDICATOR_2"] == "VOLUME":
        # Only trade if volume > average
        df.loc[df["volume_ratio"] < 1.0, "position"] = 0
    
    if config["INDICATOR_2"] == "RSI":
        # Don't buy if already overbought, don't short if oversold
        if config["INDICATOR_1"] == "EMA_CROSS":
            df.loc[(df["position"] == 1) & (df["rsi"] > 70), "position"] = 0
            df.loc[(df["position"] == -1) & (df["rsi"] < 30), "position"] = 0
    
    return df

@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    position: str  # "LONG" or "SHORT"
    pnl_pct: float
    exit_reason: str  # "SIGNAL", "STOP", "TARGET"

def backtest_strategy(df: pd.DataFrame, config: dict) -> Tuple[List[Trade], pd.DataFrame]:
    """
    Run backtest with stop losses and take profits.
    Returns list of trades and equity curve.
    """
    df = calculate_indicators(df, config)
    df = generate_signals(df, config)
    
    trades = []
    equity = []
    in_trade = False
    entry_price = 0
    entry_date = None
    position_type = None
    
    for i, row in df.iterrows():
        current_price = row["close"]
        current_date = i
        
        if not in_trade:
            # Check for entry signal
            if row.get("position") == 1:  # Buy signal
                in_trade = True
                entry_price = current_price
                entry_date = current_date
                position_type = "LONG"
            elif row.get("position") == -1:  # Short signal
                in_trade = True
                entry_price = current_price
                entry_date = current_date
                position_type = "SHORT"
        else:
            # Check exit conditions
            exit_trade = False
            exit_reason = "SIGNAL"
            
            # Calculate P&L
            if position_type == "LONG":
                pnl_pct = (current_price - entry_price) / entry_price * 100
                # Stop loss
                if pnl_pct <= -config["STOP_LOSS_PCT"]:
                    exit_trade = True
                    exit_reason = "STOP"
                # Take profit
                elif config["TAKE_PROFIT_PCT"] > 0 and pnl_pct >= config["TAKE_PROFIT_PCT"]:
                    exit_trade = True
                    exit_reason = "TARGET"
                # Signal reversal
                elif row.get("position") == -1:
                    exit_trade = True
                    exit_reason = "SIGNAL"
            else:  # SHORT
                pnl_pct = (entry_price - current_price) / entry_price * 100
                # Stop loss (price went up)
                if -pnl_pct <= -config["STOP_LOSS_PCT"]:
                    exit_trade = True
                    exit_reason = "STOP"
                # Take profit
                elif config["TAKE_PROFIT_PCT"] > 0 and -pnl_pct >= config["TAKE_PROFIT_PCT"]:
                    exit_trade = True
                    exit_reason = "TARGET"
                # Signal reversal
                elif row.get("position") == 1:
                    exit_trade = True
                    exit_reason = "SIGNAL"
            
            if exit_trade:
                trade = Trade(
                    entry_date=entry_date,
                    exit_date=current_date,
                    entry_price=entry_price,
                    exit_price=current_price,
                    position=position_type,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason
                )
                trades.append(trade)
                in_trade = False
        
        # Track equity
        equity.append({
            "date": current_date,
            "price": current_price,
            "in_trade": in_trade
        })
    
    equity_df = pd.DataFrame(equity).set_index("date")
    return trades, equity_df

# ============================================================================
# AGENT INSTRUCTIONS
# ============================================================================
"""
TO MODIFY THIS STRATEGY:

1. Change parameters in STRATEGY_CONFIG dictionary
2. Add new indicators in calculate_indicators()
3. Modify entry/exit logic in generate_signals()
4. Test with: python backtest.py

START SIMPLE:
- Try different EMA periods first (5/10, 10/20, 20/50)
- Then test RSI mean reversion (30/70 levels)
- Then add volume or RSI as filter

MEASURE RESULTS:
- Win rate must improve
- Profit factor should increase
- Max drawdown should stay under 15%
"""
