#!/usr/bin/env python3
"""
Fill forward returns on logged plays (1d / 5d / 10d) for performance review.

Usage:
  python outcome_tracker.py
  python outcome_tracker.py --report
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from momentum_history import HISTORY_FILE, load_recent

logger = logging.getLogger(__name__)
OUTCOMES_FILE = HISTORY_FILE.replace(".jsonl", "_outcomes.jsonl")


def _fwd_return(ticker: str, from_date: str, days: int) -> Optional[float]:
    try:
        start = pd.Timestamp(from_date) - timedelta(days=5)
        end = pd.Timestamp(from_date) + timedelta(days=days + 10)
        df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        if df is None or df.empty:
            return None
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        base_idx = df.index.get_indexer([pd.Timestamp(from_date)], method="nearest")[0]
        if base_idx < 0 or base_idx >= len(df):
            base_idx = len(df) - days - 2
        exit_idx = min(len(df) - 1, base_idx + days)
        if exit_idx <= base_idx:
            return None
        p0 = float(df["Close"].iloc[base_idx])
        p1 = float(df["Close"].iloc[exit_idx])
        if p0 <= 0:
            return None
        return round((p1 / p0 - 1) * 100, 2)
    except Exception as e:
        logger.debug("%s fwd return: %s", ticker, e)
        return None


def _signed_return(direction: str, raw_pct: Optional[float]) -> Optional[float]:
    if raw_pct is None:
        return None
    return raw_pct if direction == "BUY" else -raw_pct


def update_play_outcomes(record: Dict[str, Any]) -> Dict[str, Any]:
    """Attach outcomes to each play in a history record."""
    scan_date = (record.get("scan_time") or record.get("timestamp", ""))[:10]
    if not scan_date:
        scan_date = datetime.now().strftime("%Y-%m-%d")

    for play in record.get("plays") or []:
        if play.get("outcomes"):
            continue
        ticker = play.get("ticker")
        direction = play.get("direction", "BUY")
        if not ticker:
            continue
        outcomes = {}
        for horizon in (1, 5, 10):
            raw = _fwd_return(ticker, scan_date, horizon)
            outcomes[f"ret_{horizon}d"] = _signed_return(direction, raw)
        play["outcomes"] = outcomes
    record["outcomes_updated"] = datetime.now().isoformat()
    return record


def process_history(last_n: int = 30) -> int:
    records = load_recent(last_n)
    if not records:
        logger.info("No history to process")
        return 0
    updated = 0
    with open(OUTCOMES_FILE, "a") as out_f:
        for rec in records:
            if rec.get("outcomes_updated"):
                continue
            rec = update_play_outcomes(rec)
            out_f.write(json.dumps(rec) + "\n")
            updated += 1
    return updated


def report_outcomes(last_n: int = 50) -> str:
    """Summarize play-type win rates from outcomes file."""
    if not __import__("os").path.exists(OUTCOMES_FILE):
        return "No outcomes file yet. Run: python outcome_tracker.py"

    by_type: Dict[str, List[float]] = {}
    lines = ["", "=" * 60, "  PLAY OUTCOME REPORT (5d, signed return %)", "=" * 60]

    with open(OUTCOMES_FILE) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for play in rec.get("plays") or []:
                o = play.get("outcomes") or {}
                r5 = o.get("ret_5d")
                if r5 is None:
                    continue
                pt = play.get("play_type", "unknown")
                by_type.setdefault(pt, []).append(float(r5))

    for pt, rets in sorted(by_type.items()):
        wins = sum(1 for r in rets if r > 0)
        avg = sum(rets) / len(rets) if rets else 0
        lines.append(
            f"  {pt:18s}  n={len(rets):3d}  win%={100*wins/len(rets):5.1f}  avg5d={avg:+.2f}%"
        )
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--last", type=int, default=30)
    args = parser.parse_args()
    if args.report:
        print(report_outcomes())
    else:
        n = process_history(args.last)
        print(f"Updated {n} scan records → {OUTCOMES_FILE}")
        if n:
            print(report_outcomes())


if __name__ == "__main__":
    main()
