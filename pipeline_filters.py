"""Regime, macro, residual spread, theme, and portfolio filters for pipeline v2."""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from momentum_chain import MACRO_NODES
from pipeline_config import (
    DISABLE_BUY,
    GAP_MIN,
    LEADER_MOVE_MIN,
    MAX_PER_THEME,
    MAX_TRADES_PER_SCAN,
    REGIME_SPY_LONG_MIN,
    REGIME_SPY_SHORT_MAX,
    RESIDUAL_Z_MIN,
    VIX_PANIC_1D,
)

# Thematic clusters — max one open idea per bucket
THEME_BUCKETS: Dict[str, Set[str]] = {
    "space": {"RKLB", "LUNR", "ASTS", "SPCE", "RDW", "PL", "BA", "ACHR", "JOBY"},
    "crypto_proxy": {"COIN", "MSTR", "MARA", "RIOT", "HOOD", "SQ"},
    "semis": {"NVDA", "AMD", "SMCI", "AVGO", "INTC", "MU", "QCOM", "AMAT", "LRCX"},
    "meme": {"GME", "AMC", "BB", "KOSS"},
}


def theme_of(ticker: str) -> str:
    t = ticker.upper()
    for name, syms in THEME_BUCKETS.items():
        if t in syms:
            return name
    return t[:4] if len(t) >= 4 else t


def _prior_ret(rets: pd.DataFrame, sym: str, end_idx: int) -> Optional[float]:
    if sym not in rets.columns or end_idx < 1:
        return None
    return float(rets[sym].iloc[end_idx]) * 100


def spread_zscore(
    rets: pd.DataFrame,
    focus: str,
    leader: str,
    corr: float,
    end_idx: int,
    window: int = 20,
) -> Optional[float]:
    if focus not in rets.columns or leader not in rets.columns:
        return None
    if end_idx < window + 2:
        return None
    sub = rets[[focus, leader]].iloc[end_idx - window : end_idx + 1].dropna()
    if len(sub) < window // 2 + 3:
        return None
    spread = sub[focus] - corr * sub[leader]
    mu = float(spread.iloc[:-1].mean())
    sd = float(spread.iloc[:-1].std())
    if sd < 1e-8:
        return 0.0
    return float((spread.iloc[-1] - mu) / sd)


def macro_agrees(direction: str, leader_prior_pct: float, spy_ret: float, qqq_ret: float) -> bool:
    """Macro must not fight the trade (prior-day SPY/QQQ)."""
    if direction == "SHORT":
        return spy_ret <= REGIME_SPY_SHORT_MAX and qqq_ret <= REGIME_SPY_SHORT_MAX
    return spy_ret >= REGIME_SPY_LONG_MIN or (spy_ret + qqq_ret) / 2 >= REGIME_SPY_LONG_MIN


def regime_allows(
    direction: str,
    spy_ret: Optional[float],
    qqq_ret: Optional[float],
    vix_ret: Optional[float],
) -> Tuple[bool, str]:
    spy = spy_ret if spy_ret is not None else 0.0
    qqq = qqq_ret if qqq_ret is not None else 0.0
    vix = vix_ret if vix_ret is not None else 0.0
    if direction == "BUY" and vix >= VIX_PANIC_1D:
        return False, "VIX spike — no new longs"
    if not macro_agrees(direction, 0, spy, qqq):
        return False, "macro disagrees (SPY/QQQ)"
    return True, ""


def residual_allows(direction: str, z: Optional[float], fade: bool = True) -> Tuple[bool, str]:
    if z is None:
        return False, "insufficient spread history"
    # Fade: high z + leader fell → we BUY focus; low z + leader rose → we SHORT
    if fade:
        if direction == "BUY" and z < RESIDUAL_Z_MIN:
            return False, f"spread z {z:.2f} too low for fade long"
        if direction == "SHORT" and z > -RESIDUAL_Z_MIN:
            return False, f"spread z {z:.2f} too high for fade short"
        return True, ""
    if direction == "SHORT" and z < RESIDUAL_Z_MIN:
        return False, f"spread z {z:.2f} < {RESIDUAL_Z_MIN}"
    if direction == "BUY" and z > -RESIDUAL_Z_MIN:
        return False, f"spread z {z:.2f} > {-RESIDUAL_Z_MIN}"
    return True, ""


def base_signal_valid(
    lag_days: int,
    leader_prior_pct: float,
    focus_move_pct: float,
) -> Tuple[bool, str]:
    # Prior-day leader move is required; corr lag may be 0 (same-day cluster avoided by T-1 move rule)
    if abs(leader_prior_pct) < LEADER_MOVE_MIN:
        return False, f"leader move {leader_prior_pct:.1f}% < {LEADER_MOVE_MIN}%"
    if abs(focus_move_pct) >= abs(leader_prior_pct) - GAP_MIN:
        return False, "focus already caught up"
    return True, ""


def filter_candidate(
    *,
    focus: str,
    leader: str,
    direction: str,
    prediction_type: str,
    lag_days: int,
    leader_prior_pct: float,
    focus_move_pct: float,
    corr: float,
    rets: pd.DataFrame,
    end_idx: int,
) -> Tuple[bool, str]:
    ok, msg = base_signal_valid(lag_days, leader_prior_pct, focus_move_pct)
    if not ok:
        return False, msg

    spy = _prior_ret(rets, "SPY", end_idx)
    qqq = _prior_ret(rets, "QQQ", end_idx)
    vix = _prior_ret(rets, "^VIX", end_idx)
    ok, msg = regime_allows(direction, spy, qqq, vix)
    if not ok:
        return False, msg

    z = spread_zscore(rets, focus, leader, corr, end_idx)
    ok, msg = residual_allows(direction, z, fade=True)
    if not ok:
        return False, msg

    if DISABLE_BUY and direction == "BUY":
        return False, "BUY disabled (underperformed in backtest)"

    if leader in MACRO_NODES:
        return False, "macro-only leader"

    return True, ""


def select_portfolio(
    predictions: List,
    max_trades: int = MAX_TRADES_PER_SCAN,
    max_per_theme: int = MAX_PER_THEME,
) -> Tuple[List, List[str]]:
    """Pick top predictions with theme / count caps."""
    chosen: List = []
    blocked: List[str] = []
    theme_counts: Dict[str, int] = {}

    for p in predictions:
        if len(chosen) >= max_trades:
            blocked.append(f"{p.focus}: daily cap {max_trades}")
            continue
        th = theme_of(p.focus)
        if theme_counts.get(th, 0) >= max_per_theme:
            blocked.append(f"{p.focus}: theme {th} cap")
            continue
        chosen.append(p)
        theme_counts[th] = theme_counts.get(th, 0) + 1

    return chosen, blocked
