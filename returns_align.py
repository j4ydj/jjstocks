"""Aligned return matrices and move helpers for multi-calendar global universes."""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import pandas as pd

from momentum_chain import MACRO_NODES, daily_returns, min_dollar_volume

# 6mo Yahoo history ≈ 126 sessions; requiring 130 bars yields an empty matrix.
PIPELINE_MIN_BARS = int(os.getenv("PIPELINE_MIN_BARS", "60"))
PIPELINE_MIN_DV = float(os.getenv("PIPELINE_MIN_DV", "5000000"))


def build_returns_matrix(
    data: Dict[str, pd.DataFrame],
    min_bars: Optional[int] = None,
) -> pd.DataFrame:
    mb = min_bars if min_bars is not None else PIPELINE_MIN_BARS
    series = {}
    for sym, df in data.items():
        if df is None or len(df) < mb:
            continue
        if min_dollar_volume(df) < PIPELINE_MIN_DV and sym not in MACRO_NODES:
            continue
        r = daily_returns(df["Close"])
        if len(r) >= mb:
            series[sym] = r
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index()


def last_valid_end_idx(rets: pd.DataFrame) -> int:
    if rets.empty:
        return -1
    return len(rets) - 1


def _sym_returns(rets: pd.DataFrame, sym: str) -> pd.Series:
    if sym not in rets.columns:
        return pd.Series(dtype=float)
    return rets[sym].dropna()


def ret_pct(rets: pd.DataFrame, sym: str, end_idx: int = -1, offset: int = 0) -> float:
    """Last available daily return for sym (handles HK/JP/EU missing US session rows)."""
    s = _sym_returns(rets, sym)
    if len(s) <= offset:
        return 0.0
    v = s.iloc[-1 - offset]
    return float(v) * 100


def ret_5d_pct(rets: pd.DataFrame, sym: str, end_idx: int = -1) -> float:
    s = _sym_returns(rets, sym)
    if len(s) < 6:
        return 0.0
    a, b = s.iloc[-6], s.iloc[-1]
    if a == 0 or pd.isna(a) or pd.isna(b):
        return 0.0
    return float((1 + b) / (1 + a) - 1) * 100


def last_price(data: Dict[str, pd.DataFrame], sym: str) -> float:
    df = data.get(sym)
    if df is None or df.empty:
        su = sym.upper()
        for k, v in data.items():
            if k.upper() == su:
                df = v
                break
    if df is None or df.empty or "Close" not in df.columns:
        return 0.0
    c = df["Close"].dropna()
    if c.empty:
        return 0.0
    v = float(c.iloc[-1])
    return round(v, 2) if v == v else 0.0


def moves_from_rets(
    data: Dict[str, pd.DataFrame],
    rets: pd.DataFrame,
    sym: str,
    end_idx: int,
) -> Tuple[float, float, float]:
    """price, 1d%, 5d% using aligned returns + last close."""
    return (
        last_price(data, sym),
        round(ret_pct(rets, sym, end_idx), 2),
        round(ret_5d_pct(rets, sym, end_idx), 2),
    )
