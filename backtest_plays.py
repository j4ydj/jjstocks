#!/usr/bin/env python3
"""
Walk-forward backtest of momentum play rules on historical daily bars.

Usage:
  python backtest_plays.py
  python backtest_plays.py --tickers RKLB,ASTS,SMCI --years 2
"""
from __future__ import annotations

import argparse
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_TICKERS = [
    "RKLB", "ASTS", "LUNR", "SMCI", "IONQ", "PLTR", "COIN", "MSTR",
    "NVDA", "AMD", "GME", "JOBY",
]
HOLD_DAYS = 10


def _atr_pct_slice(df: pd.DataFrame, end: int, period: int = 14) -> float:
    if end < period + 2:
        return 5.0
    sl = df.iloc[end - period : end]
    h, l = sl["High"].values, sl["Low"].values
    c_prev = df["Close"].values[end - period - 1 : end - 1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - c_prev), np.abs(l - c_prev)))
    atr = float(np.mean(tr))
    price = float(df["Close"].iloc[end - 1])
    return (atr / price * 100) if price > 0 else 5.0


def simulate_play(
    df: pd.DataFrame,
    entry_idx: int,
    direction: str,
    hold_days: int = HOLD_DAYS,
) -> Optional[Dict]:
    if entry_idx + hold_days >= len(df):
        return None
    entry = float(df["Close"].iloc[entry_idx])
    atr_pct = _atr_pct_slice(df, entry_idx)
    risk_pct = min(8.0, max(2.0, atr_pct * 2))

    if direction == "BUY":
        stop = entry * (1 - risk_pct / 100)
        target = entry * (1 + 2 * risk_pct / 100)
    else:
        stop = entry * (1 + risk_pct / 100)
        target = entry * (1 - 2 * risk_pct / 100)

    exit_idx = entry_idx + hold_days
    exit_price = float(df["Close"].iloc[exit_idx])
    hit_stop = hit_target = False

    for j in range(entry_idx + 1, exit_idx + 1):
        hi = float(df["High"].iloc[j])
        lo = float(df["Low"].iloc[j])
        if direction == "BUY":
            if lo <= stop:
                exit_price, hit_stop, exit_idx = stop, True, j
                break
            if hi >= target:
                exit_price, hit_target, exit_idx = target, True, j
                break
        else:
            if hi >= stop:
                exit_price, hit_stop, exit_idx = stop, True, j
                break
            if lo <= target:
                exit_price, hit_target, exit_idx = target, True, j
                break

    if direction == "BUY":
        ret = (exit_price / entry - 1) * 100
    else:
        ret = (entry / exit_price - 1) * 100

    return {
        "return_pct": round(ret, 2),
        "hold_days": exit_idx - entry_idx,
        "hit_stop": hit_stop,
        "hit_target": hit_target,
    }


def signals_pullback(df: pd.DataFrame, i: int) -> bool:
    if i < 6:
        return False
    c = df["Close"]
    r5 = (c.iloc[i] / c.iloc[i - 5] - 1) * 100
    r1 = (c.iloc[i] / c.iloc[i - 1] - 1) * 100
    return r5 > 6 and r1 < -2


def signals_chain_short(df: pd.DataFrame, i: int) -> bool:
    if i < 6:
        return False
    c = df["Close"]
    r5 = (c.iloc[i] / c.iloc[i - 5] - 1) * 100
    r1 = (c.iloc[i] / c.iloc[i - 1] - 1) * 100
    return r5 < -5 and r1 < -2


def signals_chain_long(df: pd.DataFrame, i: int) -> bool:
    if i < 6:
        return False
    c = df["Close"]
    r5 = (c.iloc[i] / c.iloc[i - 5] - 1) * 100
    r1 = (c.iloc[i] / c.iloc[i - 1] - 1) * 100
    return r5 > 5 and r1 > 1


RULES = {
    "pullback_buy": (signals_pullback, "BUY"),
    "chain_long": (signals_chain_long, "BUY"),
    "chain_short": (signals_chain_short, "SHORT"),
}


def backtest_ticker(ticker: str, period: str = "2y") -> Dict[str, List[float]]:
    df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if df is None or len(df) < 80:
        return {}
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    results: Dict[str, List[float]] = {k: [] for k in RULES}
    step = 5
    for i in range(60, len(df) - HOLD_DAYS - 1, step):
        for name, (fn, direction) in RULES.items():
            if fn(df, i):
                sim = simulate_play(df, i + 1, direction)
                if sim:
                    results[name].append(sim["return_pct"])
    return results


def run_backtest(tickers: List[str], period: str = "2y") -> str:
    agg: Dict[str, List[float]] = {k: [] for k in RULES}
    lines = [
        "",
        "=" * 64,
        f"  PLAY RULE BACKTEST  ({period}, hold {HOLD_DAYS}d)",
        "=" * 64,
    ]

    for t in tickers:
        res = backtest_ticker(t, period=period)
        for k, vals in res.items():
            agg[k].extend(vals)

    for name, rets in agg.items():
        if not rets:
            lines.append(f"  {name:16s}  no signals")
            continue
        wins = sum(1 for r in rets if r > 0)
        avg = sum(rets) / len(rets)
        lines.append(
            f"  {name:16s}  n={len(rets):4d}  win%={100*wins/len(rets):5.1f}  "
            f"avg={avg:+.2f}%  med={sorted(rets)[len(rets)//2]:+.2f}%"
        )
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str, default=",".join(DEFAULT_TICKERS))
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    print(run_backtest(tickers, period=f"{args.years}y"))


if __name__ == "__main__":
    main()
