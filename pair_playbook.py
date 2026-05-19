#!/usr/bin/env python3
"""
Walk-forward pair playbook: only trade combinations with proven high win rate.

  python pair_playbook.py --rebuild --csv data/BACKTEST_PIPELINE_TRADES.csv
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from pipeline_config import (
    MIN_PAIR_HISTORY,
    PLAYBOOK_FILE,
    TARGET_WIN_RATE,
)

PairKey = Tuple[str, str, str, str]  # focus, leader, direction, prediction_type


def _key(focus: str, leader: str, direction: str, prediction_type: str) -> PairKey:
    return (focus.upper(), leader.upper(), direction.upper(), prediction_type)


def pair_key_str(k: PairKey) -> str:
    return f"{k[0]}/{k[1]}|{k[2]}|{k[3]}"


def history_stats(returns: List[float]) -> Dict[str, Any]:
    if not returns:
        return {"n": 0, "win_rate": 0.0, "avg_return": 0.0}
    wins = sum(1 for r in returns if r > 0)
    return {
        "n": len(returns),
        "win_rate": round(100 * wins / len(returns), 1),
        "avg_return": round(float(sum(returns) / len(returns)), 2),
    }


class PairPlaybook:
    """Rolling walk-forward: only allow trade if past outcomes meet target win rate."""

    def __init__(
        self,
        target_win_rate: float = TARGET_WIN_RATE,
        min_history: int = MIN_PAIR_HISTORY,
    ):
        self.target_win_rate = target_win_rate
        self.min_history = min_history
        self._history: Dict[PairKey, List[float]] = defaultdict(list)
        self._static_allowed: Dict[PairKey, Dict[str, Any]] = {}

    def load_static(self, path: Optional[str] = None) -> None:
        path = path or PLAYBOOK_FILE
        if not os.path.exists(path):
            return
        try:
            with open(path) as fh:
                data = json.load(fh)
            for row in data.get("allowed", []):
                k = _key(
                    row["focus"],
                    row["leader"],
                    row["direction"],
                    row.get("prediction_type", "direct_follow"),
                )
                self._static_allowed[k] = row
        except Exception:
            pass

    def allows_walkforward(
        self,
        focus: str,
        leader: str,
        direction: str,
        prediction_type: str,
    ) -> Tuple[bool, str]:
        k = _key(focus, leader, direction, prediction_type)
        hist = self._history[k]
        if len(hist) < self.min_history:
            return False, f"pair history {len(hist)}/{self.min_history}"
        st = history_stats(hist)
        if st["win_rate"] < self.target_win_rate:
            return False, f"pair win {st['win_rate']}% < {self.target_win_rate}%"
        if st["avg_return"] <= 0:
            return False, f"pair avg return {st['avg_return']}%"
        return True, ""

    def allows_static(
        self,
        focus: str,
        leader: str,
        direction: str,
        prediction_type: str,
    ) -> Tuple[bool, str]:
        k = _key(focus, leader, direction, prediction_type)
        row = self._static_allowed.get(k)
        if not row:
            return False, "not in static playbook"
        if row.get("win_rate", 0) < self.target_win_rate:
            return False, "static win below target"
        return True, ""

    def allows(
        self,
        focus: str,
        leader: str,
        direction: str,
        prediction_type: str,
        *,
        use_static: bool = False,
    ) -> Tuple[bool, str]:
        if use_static and self._static_allowed:
            return self.allows_static(focus, leader, direction, prediction_type)
        return self.allows_walkforward(focus, leader, direction, prediction_type)

    def record(
        self,
        focus: str,
        leader: str,
        direction: str,
        prediction_type: str,
        return_pct: float,
    ) -> None:
        self._history[_key(focus, leader, direction, prediction_type)].append(return_pct)

    def build_static_from_trades(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        buckets: Dict[PairKey, List[float]] = defaultdict(list)
        for t in trades:
            k = _key(
                t.get("focus", t.get("ticker", "")),
                t.get("leader", ""),
                t.get("direction", ""),
                t.get("prediction_type", t.get("setup_type", "direct_follow")),
            )
            buckets[k].append(float(t.get("return_pct", 0)))

        allowed = []
        for k, rets in buckets.items():
            st = history_stats(rets)
            if st["n"] >= self.min_history and st["win_rate"] >= self.target_win_rate and st["avg_return"] > 0:
                allowed.append({
                    "focus": k[0],
                    "leader": k[1],
                    "direction": k[2],
                    "prediction_type": k[3],
                    **st,
                })
        allowed.sort(key=lambda x: (-x["win_rate"], -x["n"]))
        return {
            "updated": datetime.now().isoformat(),
            "target_win_rate": self.target_win_rate,
            "min_pair_history": self.min_history,
            "allowed_count": len(allowed),
            "allowed": allowed,
        }

    def save(self, doc: Dict[str, Any], path: Optional[str] = None) -> str:
        path = path or PLAYBOOK_FILE
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=2)
        self._static_allowed.clear()
        for row in doc.get("allowed", []):
            k = _key(row["focus"], row["leader"], row["direction"], row["prediction_type"])
            self._static_allowed[k] = row
        return path


def rebuild_from_csv(csv_path: str, target: float = TARGET_WIN_RATE) -> str:
    df = pd.read_csv(csv_path)
    trades = df.to_dict("records")
    pb = PairPlaybook(target_win_rate=target)
    doc = pb.build_static_from_trades(trades)
    return pb.save(doc)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--rebuild", action="store_true")
    p.add_argument("--csv", default="data/BACKTEST_PIPELINE_TRADES.csv")
    args = p.parse_args()
    if args.rebuild:
        path = rebuild_from_csv(args.csv)
        with open(path) as fh:
            doc = json.load(fh)
        print(f"Playbook → {path} ({doc['allowed_count']} pairs @ >={TARGET_WIN_RATE}% win)")
    else:
        pb = PairPlaybook()
        pb.load_static()
        print(f"Loaded {len(pb._static_allowed)} allowed pairs from {PLAYBOOK_FILE}")


if __name__ == "__main__":
    main()
