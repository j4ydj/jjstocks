"""ATR-based entry, stop, target, and position sizing for chain plays."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd


@dataclass
class TradeLevels:
    ticker: str
    direction: str
    entry_price: float
    stop_loss: float
    target_price: float
    risk_pct: float
    reward_pct: float
    risk_reward: float
    position_pct: float
    exit_date: str
    conviction: int
    slippage_pct: float = 1.0


def calculate_levels(
    ticker: str,
    direction: str,
    df: pd.DataFrame,
    conviction: int = 3,
    hold_days: int = 10,
) -> Optional[TradeLevels]:
    if df is None or len(df) < 20:
        return None

    entry = float(df["Close"].iloc[-1])
    if entry <= 0:
        return None

    high = df["High"].values[-14:]
    low = df["Low"].values[-14:]
    close_prev = df["Close"].values[-15:-1]
    tr = np.maximum(high - low, np.maximum(abs(high - close_prev), abs(low - close_prev)))
    atr = float(np.mean(tr))
    if atr <= 0:
        return None

    if direction == "BUY":
        swing_low = float(df["Low"].iloc[-10:].min())
        stop = max(entry - (2.0 * atr), swing_low)
        risk_pct = (entry - stop) / entry * 100
        if risk_pct > 8 or risk_pct < 1:
            stop = entry * 0.95
            risk_pct = 5.0
        target = entry + (entry - stop) * 2.0
        reward_pct = (target - entry) / entry * 100
    else:
        swing_high = float(df["High"].iloc[-10:].max())
        stop = min(entry + (2.0 * atr), swing_high)
        risk_pct = (stop - entry) / entry * 100
        if risk_pct > 8 or risk_pct < 1:
            stop = entry * 1.05
            risk_pct = 5.0
        target = entry - (stop - entry) * 2.0
        reward_pct = (entry - target) / entry * 100

    risk_reward = reward_pct / risk_pct if risk_pct > 0 else 0
    portfolio_risk_pct = {3: 1.0, 4: 1.25, 5: 1.5}.get(conviction, 1.25)
    position_pct = min(20.0, (portfolio_risk_pct / risk_pct) * 100) if risk_pct > 0 else 1.5

    return TradeLevels(
        ticker=ticker,
        direction=direction,
        entry_price=round(entry, 2),
        stop_loss=round(stop, 2),
        target_price=round(target, 2),
        risk_pct=round(risk_pct, 1),
        reward_pct=round(reward_pct, 1),
        risk_reward=round(risk_reward, 1),
        position_pct=round(position_pct, 1),
        exit_date=(datetime.now() + timedelta(days=hold_days)).strftime("%Y-%m-%d"),
        conviction=conviction,
    )
