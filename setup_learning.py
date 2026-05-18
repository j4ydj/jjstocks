#!/usr/bin/env python3
"""
Learn which setup / pair / direction combinations lose money and filter them live.

Sources (merged):
  1. data/BACKTEST_SETUPS_2Y.csv (or 1Y) — historical simulation
  2. data/trade_setups.jsonl — your forward log (updates as trades close)

Scores written to: data/setup_scores.json

Rebuild scores:
  python setup_learning.py --rebuild
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from chain_setups import TradeSetup

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
SCORES_FILE = os.path.join(DATA_DIR, "setup_scores.json")
BACKTEST_CSV = os.path.join(DATA_DIR, "BACKTEST_SETUPS_2Y.csv")
if not os.path.exists(BACKTEST_CSV):
    BACKTEST_CSV = os.path.join(DATA_DIR, "BACKTEST_SETUPS.csv")
LIVE_LOG = os.path.join(DATA_DIR, "trade_setups.jsonl")

MIN_SAMPLES_BLOCK = int(os.getenv("LEARN_MIN_SAMPLES", "15"))
MAX_WIN_RATE_BLOCK = float(os.getenv("LEARN_MAX_WIN_BLOCK", "32"))
MIN_AVG_RETURN_BLOCK = float(os.getenv("LEARN_MIN_AVG_BLOCK", "-0.5"))
REQUIRE_LEAD_LAG = os.getenv("REQUIRE_LEAD_LAG", "1") == "1"
REQUIRE_LEADER_PRIOR_DAY = os.getenv("REQUIRE_LEADER_PRIOR_DAY", "1") == "1"
DISABLE_DIVERGENCE = os.getenv("DISABLE_DIVERGENCE", "1") == "1"
DISABLE_BUY_CATCHUP = os.getenv("DISABLE_BUY_CATCHUP", "1") == "1"


def _load_backtest() -> pd.DataFrame:
    if not os.path.exists(BACKTEST_CSV):
        return pd.DataFrame()
    df = pd.read_csv(BACKTEST_CSV)
    df["pair"] = df["focus"] + "/" + df["leader"]
    df["win"] = df["win"].astype(bool) if "win" in df.columns else (df["return_pct"] > 0)
    return df


def _load_live() -> pd.DataFrame:
    if not os.path.exists(LIVE_LOG):
        return pd.DataFrame()
    rows = []
    for line in open(LIVE_LOG):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("setup_type") in ("scan_heartbeat", "none") or not r.get("ticker"):
            continue
        o = r.get("outcomes") or {}
        ret5 = o.get("ret_5d")
        if ret5 is None:
            continue
        rows.append({
            "focus": r["ticker"],
            "leader": r.get("leader", ""),
            "setup_type": r.get("setup_type", ""),
            "direction": r.get("direction", ""),
            "pair": f"{r['ticker']}/{r.get('leader', '')}",
            "return_pct": ret5,
            "win": ret5 > 0,
            "source": "live",
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _agg(df: pd.DataFrame, key: str) -> Dict[str, Dict[str, Any]]:
    if df.empty or key not in df.columns:
        return {}
    out = {}
    for name, g in df.groupby(key):
        n = len(g)
        if n == 0:
            continue
        out[str(name)] = {
            "n": int(n),
            "win_rate": round(100 * g["win"].mean(), 1),
            "avg_return": round(float(g["return_pct"].mean()), 2),
        }
    return out


def rebuild_scores() -> Dict[str, Any]:
    bt = _load_backtest()
    live = _load_live()
    combined = pd.concat([bt, live], ignore_index=True) if not live.empty else bt

    by_type = _agg(combined, "setup_type")
    by_pair = _agg(combined, "pair")
    by_dir = _agg(combined, "direction")
    by_focus = _agg(combined, "focus")

    blocked_pairs = []
    for pair, stats in by_pair.items():
        if stats["n"] >= MIN_SAMPLES_BLOCK:
            if stats["win_rate"] <= MAX_WIN_RATE_BLOCK and stats["avg_return"] <= MIN_AVG_RETURN_BLOCK:
                blocked_pairs.append(pair)

    blocked_focus = []
    for foc, stats in by_focus.items():
        if stats["n"] >= MIN_SAMPLES_BLOCK * 2:
            if stats["win_rate"] <= MAX_WIN_RATE_BLOCK - 5:
                blocked_focus.append(foc)

    scores = {
        "updated": pd.Timestamp.now().isoformat(),
        "sources": {
            "backtest_rows": len(bt),
            "live_rows": len(live),
            "backtest_file": BACKTEST_CSV,
        },
        "overall": _agg(combined, "setup_type").get("catch_up", {}),
        "by_setup_type": by_type,
        "by_direction": by_dir,
        "by_pair": by_pair,
        "blocked_pairs": sorted(blocked_pairs),
        "blocked_focus": sorted(blocked_focus),
        "rules": {
            "require_lead_lag_days_min": 1 if REQUIRE_LEAD_LAG else 0,
            "require_leader_prior_day": REQUIRE_LEADER_PRIOR_DAY,
            "disable_divergence": DISABLE_DIVERGENCE,
            "disable_buy_catchup": DISABLE_BUY_CATCHUP,
        },
        "lessons": [
            "Directional hit rate ≠ trade win rate (hits measure same-day; we enter next open).",
            "Stops trigger ~57% of the time in backtest — tight for volatile names.",
            "BUY catch-up underperformed SHORT in backtest.",
            "Divergence mean-reversion underperformed catch-up.",
        ],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCORES_FILE, "w") as fh:
        json.dump(scores, fh, indent=2)
    return scores


def load_scores() -> Dict[str, Any]:
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE) as fh:
                return json.load(fh)
        except Exception:
            pass
    return rebuild_scores()


def passes_trade_row(
    setup_type: str,
    direction: str,
    lag: int,
    focus: str,
    leader: str,
    scores: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """Filter without full TradeSetup (for backtest rows)."""
    scores = scores or load_scores()
    rules = scores.get("rules", {})
    if rules.get("disable_divergence") and setup_type == "divergence":
        return False, "divergence disabled"
    if rules.get("disable_buy_catchup") and setup_type == "catch_up" and direction == "BUY":
        return False, "BUY catch-up disabled"
    min_lag = int(rules.get("require_lead_lag_days_min", 0))
    if setup_type == "catch_up" and min_lag > 0 and lag < min_lag:
        if not rules.get("require_leader_prior_day"):
            return False, f"lag<{min_lag}"
    if setup_type == "catch_up" and rules.get("require_leader_prior_day") and lag < 1:
        return False, "same-day cluster (use leader from prior day only)"
    pair = f"{focus}/{leader}"
    if pair in scores.get("blocked_pairs", []):
        return False, "blocked pair"
    if focus in scores.get("blocked_focus", []):
        return False, "blocked focus"
    return True, ""


def filter_setup(setup: TradeSetup, scores: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Return (allowed, reason_if_blocked)."""
    scores = scores or load_scores()
    rules = scores.get("rules", {})

    if rules.get("disable_divergence") and setup.setup_type == "divergence":
        return False, "divergence disabled (poor backtest)"

    if rules.get("disable_buy_catchup") and setup.setup_type == "catch_up" and setup.direction == "BUY":
        return False, "BUY catch-up disabled (poor backtest)"

    min_lag = int(rules.get("require_lead_lag_days_min", 0))
    if setup.setup_type == "catch_up" and min_lag > 0 and setup.lag_days < min_lag:
        return False, f"catch-up requires lag≥{min_lag}d (same-day entries underperform)"

    pair = f"{setup.ticker}/{setup.leader}"
    if pair in scores.get("blocked_pairs", []):
        return False, f"pair blocked (historical win rate)"

    if setup.ticker in scores.get("blocked_focus", []):
        return False, f"focus blocked (historical win rate)"

    return True, ""


def filter_setups(setups: List[TradeSetup]) -> Tuple[List[TradeSetup], List[str]]:
    scores = load_scores()
    allowed: List[TradeSetup] = []
    blocked_msgs: List[str] = []
    for s in setups:
        ok, reason = filter_setup(s, scores)
        if ok:
            allowed.append(s)
        else:
            blocked_msgs.append(f"{s.direction} {s.ticker} ({s.setup_type}): {reason}")
    return allowed, blocked_msgs


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--rebuild", action="store_true")
    args = p.parse_args()
    scores = rebuild_scores() if args.rebuild or not os.path.exists(SCORES_FILE) else load_scores()
    print(json.dumps({
        "file": SCORES_FILE,
        "blocked_pairs": len(scores.get("blocked_pairs", [])),
        "blocked_focus": scores.get("blocked_focus", []),
        "by_setup_type": scores.get("by_setup_type", {}),
        "rules": scores.get("rules", {}),
    }, indent=2))


if __name__ == "__main__":
    main()
