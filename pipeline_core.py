#!/usr/bin/env python3
"""
Shared map-based predictions: movements, chain forecasts, trade levels, dates.
Used by backtest_map_pipeline.py and daily_pipeline.py.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from chain_stats import corr_pvalue, lead_lag_hit_rate
from correlation_map import HORIZONS, MACRO_NODES, _multi_step_paths, _relation
from momentum_chain import lead_lag_corr, min_dollar_volume
from trade_levels import calculate_levels

CORR_WINDOW = int(os.getenv("PIPELINE_CORR_WINDOW", "60"))
MIN_CORR = float(os.getenv("PIPELINE_MIN_CORR", "0.55"))
MIN_HIT = float(os.getenv("PIPELINE_MIN_HIT", "55"))
LEADER_MOVE_MIN = float(os.getenv("PIPELINE_LEADER_MOVE", "2.0"))
GAP_MIN = float(os.getenv("PIPELINE_GAP_MIN", "1.0"))
HOLD_DAYS = int(os.getenv("PIPELINE_HOLD_DAYS", "5"))


@dataclass
class MovementSnapshot:
    ticker: str
    price: float
    move_1d_pct: float
    move_5d_pct: float


@dataclass
class ChainPrediction:
    signal_date: str
    focus: str
    focus_price: float
    focus_move_1d: float
    prediction_type: str
    leader: str
    leader_move_pct: float
    chain_path: str
    direction: str
    predicted_move_pct: float
    expected_days: int
    expected_by_date: str
    corr: float
    horizon_days: int
    lag_days: int
    hit_rate: Optional[float]
    hit_n: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    risk_pct: float = 0.0
    position_pct: float = 0.0

    def to_trade_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["setup_type"] = self.prediction_type
        d["ticker"] = self.focus
        d["thesis"] = (
            f"{self.leader} moved {self.leader_move_pct:+.1f}% on {self.signal_date}; "
            f"path {self.chain_path}; predict {self.focus} {self.direction} "
            f"~{self.predicted_move_pct:+.1f}% by {self.expected_by_date} "
            f"(r={self.corr:+.2f}, {self.horizon_days}d, lag {self.lag_days}d)"
        )
        return d


def _pct(close: pd.Series, i: int) -> float:
    if i < 1:
        return 0.0
    p0, p1 = float(close.iloc[i - 1]), float(close.iloc[i])
    return (p1 / p0 - 1) * 100 if p0 > 0 else 0.0


def _attach_levels(pred: ChainPrediction, hist: pd.DataFrame) -> ChainPrediction:
    lv = calculate_levels(pred.focus, pred.direction, hist, conviction=4, hold_days=HOLD_DAYS)
    if lv:
        pred.entry_price = lv.entry_price
        pred.stop_loss = lv.stop_loss
        pred.target_price = lv.target_price
        pred.risk_pct = lv.risk_pct
        pred.position_pct = lv.position_pct
    return pred


def _edges_from_rets(
    rets: pd.DataFrame,
    focus: str,
    end_idx: int,
    min_corr: float,
) -> List[Dict[str, Any]]:
    """Rolling correlations at signal bar end_idx."""
    if focus not in rets.columns or end_idx < CORR_WINDOW + 5:
        return []
    edges = []
    for target in rets.columns:
        if target == focus:
            continue
        best_c, best_h = 0.0, CORR_WINDOW
        lag, hit, hit_n = 0, None, 0
        for h in (21, 60, 120):
            if h > end_idx:
                continue
            sub = rets[[focus, target]].iloc[end_idx - h : end_idx + 1].dropna()
            if len(sub) < h // 2 + 5:
                continue
            c = float(sub[focus].corr(sub[target]))
            if np.isnan(c) or abs(c) < min_corr:
                continue
            if abs(c) > abs(best_c):
                best_c, best_h = c, h
                lag = lead_lag_corr(sub[focus], sub[target])[1]
                hit, hit_n = lead_lag_hit_rate(sub[focus], sub[target], lag, c, min_events=8)
        if abs(best_c) < min_corr:
            continue
        if hit is not None and hit < MIN_HIT:
            continue
        edges.append({
            "target": target,
            "layer": "macro" if target in MACRO_NODES else "equity",
            "corr": best_c,
            "horizon": best_h,
            "lag": lag,
            "hit_rate": hit,
            "hit_n": hit_n,
        })
    edges.sort(key=lambda x: abs(x["corr"]), reverse=True)
    return edges


def generate_predictions(
    data: Dict[str, pd.DataFrame],
    rets: pd.DataFrame,
    focus_list: List[str],
    signal_date: str,
    end_idx: Optional[int] = None,
) -> Tuple[List[MovementSnapshot], List[ChainPrediction]]:
    """
    Generate movement snapshot + chain predictions for focus names at signal_date / bar end_idx.
    """
    if end_idx is None:
        end_idx = len(rets) - 1

    movers: List[MovementSnapshot] = []
    for sym in focus_list:
        if sym not in data:
            continue
        df = data[sym]
        if end_idx >= len(df):
            continue
        c = df["Close"]
        movers.append(
            MovementSnapshot(
                ticker=sym,
                price=round(float(c.iloc[end_idx]), 2),
                move_1d_pct=round(_pct(c, end_idx), 2),
                move_5d_pct=round(
                    (float(c.iloc[end_idx]) / float(c.iloc[end_idx - 5]) - 1) * 100
                    if end_idx >= 5 and float(c.iloc[end_idx - 5]) > 0
                    else 0.0,
                    2,
                ),
            )
        )

    predictions: List[ChainPrediction] = []
    seen = set()

    for focus in focus_list:
        if focus not in data or focus not in rets.columns:
            continue
        fdf = data[focus]
        if end_idx >= len(fdf):
            continue
        f_move = _pct(fdf["Close"], end_idx)
        edges_raw = _edges_from_rets(rets, focus, end_idx, MIN_CORR)
        if not edges_raw:
            continue

        # MapEdge-like for paths
        class _E:
            pass

        path_edges = []
        for e in edges_raw[:60]:
            o = _E()
            o.source, o.target = focus, e["target"]
            o.best_corr, o.target_layer = e["corr"], e["layer"]
            path_edges.append(o)

        paths = _multi_step_paths(focus, path_edges, max_depth=3)[:15]

        for e in edges_raw[:25]:
            target = e["target"]
            corr = e["corr"]
            lag = e["lag"]
            layer = e["layer"]
            hit = e.get("hit_rate")
            hit_n = e.get("hit_n", 0)

            if layer == "macro":
                continue

            ldf = data.get(target)
            if ldf is None or end_idx >= len(ldf):
                continue
            l_move_today = _pct(ldf["Close"], end_idx)
            l_move_prior = _pct(ldf["Close"], end_idx - 1) if end_idx >= 2 else l_move_today

            # Prior-day leader catch-up
            if abs(l_move_prior) >= LEADER_MOVE_MIN and abs(f_move) < abs(l_move_prior) - GAP_MIN:
                direction = "BUY" if (l_move_prior > 0 and corr > 0) else "SHORT"
                if corr > 0:
                    direction = "BUY" if l_move_prior > 0 else "SHORT"
                else:
                    direction = "SHORT" if l_move_prior > 0 else "BUY"
                exp_days = max(1, lag) if lag > 0 else HOLD_DAYS
                pred_move = abs(l_move_prior) * 0.6 * (1 if corr > 0 else -1)
                if direction == "SHORT":
                    pred_move = -abs(pred_move)
                key = (focus, target, "direct_follow", direction)
                if key in seen:
                    continue
                seen.add(key)
                exp_date = (pd.Timestamp(signal_date) + timedelta(days=exp_days)).strftime("%Y-%m-%d")
                p = ChainPrediction(
                    signal_date=signal_date,
                    focus=focus,
                    focus_price=round(float(fdf["Close"].iloc[end_idx]), 2),
                    focus_move_1d=f_move,
                    prediction_type="direct_follow",
                    leader=target,
                    leader_move_pct=round(l_move_prior, 2),
                    chain_path=f"{target} → {focus}",
                    direction=direction,
                    predicted_move_pct=round(pred_move, 2),
                    expected_days=exp_days,
                    expected_by_date=exp_date,
                    corr=round(corr, 3),
                    horizon_days=e["horizon"],
                    lag_days=lag,
                    hit_rate=hit,
                    hit_n=hit_n,
                )
                predictions.append(_attach_levels(p, fdf.iloc[: end_idx + 1]))

        # Chain propagation: 2-hop path, leader at start moved
        for path in paths:
            if path.hops < 2 or len(path.nodes) < 3:
                continue
            a, b, c = path.nodes[0], path.nodes[1], path.nodes[2]
            if a != focus:
                continue
            mid_df = data.get(b)
            if mid_df is None or end_idx >= len(mid_df):
                continue
            mid_move = _pct(mid_df["Close"], end_idx - 1) if end_idx >= 2 else _pct(mid_df["Close"], end_idx)
            if abs(mid_move) < LEADER_MOVE_MIN:
                continue
            f_move_now = f_move
            if abs(f_move_now) >= abs(mid_move) - GAP_MIN:
                continue
            direction = "BUY" if mid_move > 0 else "SHORT"
            key = (focus, c, "chain_propagation", direction)
            if key in seen:
                continue
            seen.add(key)
            exp_days = HOLD_DAYS
            exp_date = (pd.Timestamp(signal_date) + timedelta(days=exp_days)).strftime("%Y-%m-%d")
            pred_move = mid_move * 0.5
            if direction == "SHORT":
                pred_move = -abs(pred_move)
            p = ChainPrediction(
                signal_date=signal_date,
                focus=focus,
                focus_price=round(float(fdf["Close"].iloc[end_idx]), 2),
                focus_move_1d=f_move,
                prediction_type="chain_propagation",
                leader=b,
                leader_move_pct=round(mid_move, 2),
                chain_path=path.description,
                direction=direction,
                predicted_move_pct=round(pred_move, 2),
                expected_days=exp_days,
                expected_by_date=exp_date,
                corr=round(path.min_corr, 3),
                horizon_days=60,
                lag_days=1,
                hit_rate=None,
                hit_n=0,
            )
            predictions.append(_attach_levels(p, fdf.iloc[: end_idx + 1]))

    predictions.sort(key=lambda p: abs(p.predicted_move_pct), reverse=True)
    return movers, predictions


def simulate_prediction(
    data: Dict[str, pd.DataFrame],
    pred: ChainPrediction,
    entry_idx: int,
) -> Optional[Dict[str, Any]]:
    """Enter next bar open after signal, honor stops."""
    df = data.get(pred.focus)
    if df is None or entry_idx + 1 >= len(df):
        return None
    hist = df.iloc[: entry_idx + 1]
    lv = calculate_levels(pred.focus, pred.direction, hist, conviction=4, hold_days=HOLD_DAYS)
    if not lv:
        return None
    entry = float(df["Open"].iloc[entry_idx + 1])
    risk = abs(lv.entry_price - lv.stop_loss)
    reward = abs(lv.target_price - lv.entry_price)
    if pred.direction == "BUY":
        stop, target = entry - risk, entry + reward
    else:
        stop, target = entry + risk, entry - reward

    exit_idx = min(len(df) - 1, entry_idx + 1 + HOLD_DAYS)
    exit_price = float(df["Close"].iloc[exit_idx])
    hit_stop = hit_target = False
    for j in range(entry_idx + 1, exit_idx + 1):
        hi, lo = float(df["High"].iloc[j]), float(df["Low"].iloc[j])
        if pred.direction == "BUY":
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

    if pred.direction == "BUY":
        ret = (exit_price / entry - 1) * 100
        actual_move = ret
    else:
        ret = (entry / exit_price - 1) * 100 if exit_price > 0 else 0
        actual_move = -((exit_price / entry - 1) * 100)

    dir_ok = (actual_move > 0) == (pred.predicted_move_pct > 0)
    return {
        "entry": round(entry, 2),
        "exit": round(exit_price, 2),
        "return_pct": round(ret, 2),
        "actual_move_pct": round(actual_move, 2),
        "direction_correct": dir_ok,
        "hit_stop": hit_stop,
        "hit_target": hit_target,
        "hold_days": exit_idx - entry_idx,
    }
