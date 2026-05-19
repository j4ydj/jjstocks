#!/usr/bin/env python3
"""
Map-based predictions v2: strict filters, spread/regime gates, walk-forward playbook.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from chain_stats import lead_lag_hit_rate
from correlation_map import MACRO_NODES, _multi_step_paths
from momentum_chain import lead_lag_corr
from pair_playbook import PairPlaybook
from pipeline_config import (
    COST_BPS_PER_SIDE,
    FADE_MODE,
    HOLD_DAYS,
    MIN_CORR,
    MIN_HIT,
    MIN_LAG_DAYS,
    PARTIAL_TARGET_R,
    SPREAD_STOP_Z,
    TIME_STOP_DAYS,
)


def _trade_direction(corr: float, leader_prior_pct: float) -> str:
    """Momo catch-up vs fade (contrarian). Fade backtested far better on this universe."""
    if corr > 0:
        momo = "BUY" if leader_prior_pct > 0 else "SHORT"
    else:
        momo = "SHORT" if leader_prior_pct > 0 else "BUY"
    if not FADE_MODE:
        return momo
    return "SHORT" if momo == "BUY" else "BUY"
from pipeline_filters import filter_candidate, spread_zscore
from trade_levels import calculate_levels

# Re-export for backtest imports
CORR_WINDOW = int(os.getenv("PIPELINE_CORR_WINDOW", "60"))
GAP_MIN = float(os.getenv("PIPELINE_GAP_MIN", "1.25"))
LEADER_MOVE_MIN = float(os.getenv("PIPELINE_LEADER_MOVE", "2.5"))


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
    spread_z: float = 0.0
    filter_note: str = ""

    def to_trade_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["setup_type"] = self.prediction_type
        d["ticker"] = self.focus
        d["pipeline"] = "map_v2"
        d["thesis"] = (
            f"{self.leader} moved {self.leader_move_pct:+.1f}% (prior day); "
            f"path {self.chain_path}; {self.direction} {self.focus} "
            f"~{self.predicted_move_pct:+.1f}% by {self.expected_by_date} "
            f"(r={self.corr:+.2f}, lag {self.lag_days}d, z={self.spread_z:+.2f})"
        )
        return d


def _pct(close: pd.Series, i: int) -> float:
    if i < 1:
        return 0.0
    p0, p1 = float(close.iloc[i - 1]), float(close.iloc[i])
    return (p1 / p0 - 1) * 100 if p0 > 0 else 0.0


def _attach_levels(pred: ChainPrediction, hist: pd.DataFrame) -> ChainPrediction:
    lv = calculate_levels(pred.focus, pred.direction, hist, conviction=5, hold_days=HOLD_DAYS)
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
                hit, hit_n = lead_lag_hit_rate(sub[focus], sub[target], lag, c, min_events=10)
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


def _path_lags_valid(rets: pd.DataFrame, nodes: List[str], end_idx: int) -> bool:
    """Path legs must have meaningful correlation (lag may be 0; timing from prior-day moves)."""
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        if a not in rets.columns or b not in rets.columns:
            return False
        sub = rets[[a, b]].iloc[max(0, end_idx - 60) : end_idx + 1].dropna()
        if len(sub) < 30:
            return False
        c = float(sub[a].corr(sub[b]))
        if np.isnan(c) or abs(c) < MIN_CORR * 0.9:
            return False
    return True


def apply_playbook_and_rank(
    predictions: List[ChainPrediction],
    playbook: Optional[PairPlaybook] = None,
    *,
    use_static: bool = True,
) -> List[ChainPrediction]:
    pb = playbook or PairPlaybook()
    if use_static:
        pb.load_static()
    if use_static and not pb._static_allowed:
        return sorted(predictions, key=lambda x: abs(x.spread_z), reverse=True)
    out: List[ChainPrediction] = []
    for p in predictions:
        ok, _ = pb.allows(p.focus, p.leader, p.direction, p.prediction_type, use_static=use_static)
        if ok:
            p.filter_note = "playbook_ok"
            out.append(p)
    out.sort(key=lambda x: (abs(x.spread_z), abs(x.predicted_move_pct)), reverse=True)
    return out


def generate_predictions(
    data: Dict[str, pd.DataFrame],
    rets: pd.DataFrame,
    focus_list: List[str],
    signal_date: str,
    end_idx: Optional[int] = None,
    *,
    apply_playbook: bool = True,
) -> Tuple[List[MovementSnapshot], List[ChainPrediction]]:
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

    raw_preds: List[ChainPrediction] = []
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
            if e["layer"] == "macro":
                continue
            ldf = data.get(target)
            if ldf is None or end_idx >= len(ldf):
                continue
            l_move_prior = _pct(ldf["Close"], end_idx - 1) if end_idx >= 2 else _pct(ldf["Close"], end_idx)
            lag = e["lag"]
            corr = e["corr"]

            direction = _trade_direction(corr, l_move_prior)
            ok, _ = filter_candidate(
                focus=focus,
                leader=target,
                direction=direction,
                prediction_type="direct_follow",
                lag_days=lag,
                leader_prior_pct=l_move_prior,
                focus_move_pct=f_move,
                corr=corr,
                rets=rets,
                end_idx=end_idx,
            )
            if not ok:
                continue
            exp_days = max(MIN_LAG_DAYS, lag) if lag > 0 else HOLD_DAYS
            pred_move = abs(l_move_prior) * 0.55 * (1 if corr > 0 else -1)
            if direction == "SHORT":
                pred_move = -abs(pred_move)
            key = (focus, target, "direct_follow", direction)
            if key in seen:
                continue
            seen.add(key)
            z = spread_zscore(rets, focus, target, corr, end_idx) or 0.0
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
                hit_rate=e.get("hit_rate"),
                hit_n=e.get("hit_n", 0),
                spread_z=round(z, 2),
            )
            raw_preds.append(_attach_levels(p, fdf.iloc[: end_idx + 1]))

        for path in paths:
            if path.hops < 2 or len(path.nodes) < 3:
                continue
            if not _path_lags_valid(rets, path.nodes, end_idx):
                continue
            a, b, c = path.nodes[0], path.nodes[1], path.nodes[2]
            if a != focus:
                continue
            mid_df = data.get(b)
            if mid_df is None or end_idx >= len(mid_df):
                continue
            mid_move = _pct(mid_df["Close"], end_idx - 1) if end_idx >= 2 else _pct(mid_df["Close"], end_idx)
            corr_fb = next((x["corr"] for x in edges_raw if x["target"] == b), path.min_corr)
            direction = _trade_direction(corr_fb, mid_move)
            ok, _ = filter_candidate(
                focus=focus,
                leader=b,
                direction=direction,
                prediction_type="chain_propagation",
                lag_days=MIN_LAG_DAYS,
                leader_prior_pct=mid_move,
                focus_move_pct=f_move,
                corr=corr_fb,
                rets=rets,
                end_idx=end_idx,
            )
            if not ok:
                continue
            if abs(f_move) >= abs(mid_move) - GAP_MIN:
                continue
            key = (focus, c, "chain_propagation", direction)
            if key in seen:
                continue
            seen.add(key)
            z = spread_zscore(rets, focus, b, corr_fb, end_idx) or 0.0
            exp_date = (pd.Timestamp(signal_date) + timedelta(days=HOLD_DAYS)).strftime("%Y-%m-%d")
            pred_move = mid_move * 0.45
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
                expected_days=HOLD_DAYS,
                expected_by_date=exp_date,
                corr=round(path.min_corr, 3),
                horizon_days=60,
                lag_days=MIN_LAG_DAYS,
                hit_rate=None,
                hit_n=0,
                spread_z=round(z, 2),
            )
            raw_preds.append(_attach_levels(p, fdf.iloc[: end_idx + 1]))

    if apply_playbook:
        predictions = apply_playbook_and_rank(raw_preds, use_static=True)
    else:
        predictions = sorted(raw_preds, key=lambda p: abs(p.predicted_move_pct), reverse=True)

    return movers, predictions


def _apply_costs(return_pct: float, direction: str) -> float:
    cost = 2 * COST_BPS_PER_SIDE / 100
    return return_pct - cost


def simulate_prediction(
    data: Dict[str, pd.DataFrame],
    pred: ChainPrediction,
    entry_idx: int,
    rets: Optional[pd.DataFrame] = None,
) -> Optional[Dict[str, Any]]:
    """Next-bar open entry; time stop, partial R, spread stop, net of costs."""
    df = data.get(pred.focus)
    if df is None or entry_idx + 1 >= len(df):
        return None
    hist = df.iloc[: entry_idx + 1]
    lv = calculate_levels(pred.focus, pred.direction, hist, conviction=5, hold_days=HOLD_DAYS)
    if not lv:
        return None

    entry = float(df["Open"].iloc[entry_idx + 1])
    risk = abs(lv.entry_price - lv.stop_loss)
    reward = abs(lv.target_price - lv.entry_price)
    if pred.direction == "BUY":
        stop, target = entry - risk, entry + reward
        partial = entry + risk * PARTIAL_TARGET_R
    else:
        stop, target = entry + risk, entry - reward
        partial = entry - risk * PARTIAL_TARGET_R

    max_idx = min(len(df) - 1, entry_idx + 1 + HOLD_DAYS)
    exit_price = float(df["Close"].iloc[max_idx])
    hit_stop = hit_target = hit_partial = False
    time_stop = False

    for j in range(entry_idx + 1, max_idx + 1):
        hi, lo = float(df["High"].iloc[j]), float(df["Low"].iloc[j])
        days_in = j - entry_idx

        if rets is not None and pred.leader in rets.columns and pred.focus in rets.columns:
            z = spread_zscore(rets, pred.focus, pred.leader, pred.corr, j)
            if z is not None and abs(z) > SPREAD_STOP_Z:
                exit_price = float(df["Close"].iloc[j])
                hit_stop, time_stop = True, True
                break

        if days_in >= TIME_STOP_DAYS:
            if pred.direction == "BUY":
                if float(df["Close"].iloc[j]) <= entry:
                    exit_price = float(df["Close"].iloc[j])
                    time_stop = True
                    break
            else:
                if float(df["Close"].iloc[j]) >= entry:
                    exit_price = float(df["Close"].iloc[j])
                    time_stop = True
                    break

        if pred.direction == "BUY":
            if lo <= stop:
                exit_price, hit_stop = stop, True
                break
            if hi >= partial and not hit_partial:
                hit_partial = True
            if hi >= target:
                exit_price, hit_target = target, True
                break
        else:
            if hi >= stop:
                exit_price, hit_stop = stop, True
                break
            if lo <= partial and not hit_partial:
                hit_partial = True
            if lo <= target:
                exit_price, hit_target = target, True
                break

    if pred.direction == "BUY":
        ret = (exit_price / entry - 1) * 100
    else:
        ret = (entry / exit_price - 1) * 100 if exit_price > 0 else 0

    ret_net = _apply_costs(ret, pred.direction)
    dir_ok = (ret_net > 0) == (pred.predicted_move_pct > 0)

    return {
        "entry": round(entry, 2),
        "exit": round(exit_price, 2),
        "return_pct": round(ret_net, 2),
        "return_pct_gross": round(ret, 2),
        "actual_move_pct": round(ret_net, 2),
        "direction_correct": dir_ok,
        "hit_stop": hit_stop,
        "hit_target": hit_target,
        "hit_partial": hit_partial,
        "time_stop": time_stop,
        "hold_days": max_idx - entry_idx,
    }
