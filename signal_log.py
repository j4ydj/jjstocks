#!/usr/bin/env python3
"""Append chain alert signals and later fill forward outcomes."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from chain_ping import chains_with_moves
from momentum_chain import MomentumScanResult

SIGNAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SIGNAL_FILE = os.path.join(SIGNAL_DIR, "chain_signals.jsonl")


def _link_dict(link) -> Dict[str, Any]:
    return {
        "node": link.node,
        "layer": link.layer,
        "corr": link.corr_21d,
        "pvalue": link.corr_pvalue,
        "n": link.sample_n,
        "lag": link.lead_lag_days,
        "hit_rate": link.lag_hit_rate,
        "hit_n": link.lag_hit_n,
        "move_1d": link.move_1d_pct,
        "regime_break": link.regime_break,
    }


def log_scan(result: MomentumScanResult, hints_by_ticker: Optional[Dict[str, List[str]]] = None) -> str:
    os.makedirs(SIGNAL_DIR, exist_ok=True)
    hints_by_ticker = hints_by_ticker or {}
    for chain in chains_with_moves(result):
        f = chain.focus
        record = {
            "logged_at": datetime.now().isoformat(),
            "scan_time": result.scan_time,
            "focus": f.ticker,
            "price": f.last_price,
            "return_1d": f.return_1d_pct,
            "return_5d": f.return_5d_pct,
            "links": [_link_dict(l) for l in chain.links[:12]],
            "hints": hints_by_ticker.get(f.ticker.upper(), []),
            "outcomes": {},
        }
        with open(SIGNAL_FILE, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    return SIGNAL_FILE


def _fwd(ticker: str, from_date: str, days: int) -> Optional[float]:
    try:
        start = pd.Timestamp(from_date) - timedelta(days=5)
        end = pd.Timestamp(from_date) + timedelta(days=days + 10)
        df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        if df is None or df.empty:
            return None
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        idx = df.index.get_indexer([pd.Timestamp(from_date)], method="nearest")[0]
        exit_idx = min(len(df) - 1, idx + days)
        if exit_idx <= idx:
            return None
        p0, p1 = float(df["Close"].iloc[idx]), float(df["Close"].iloc[exit_idx])
        return round((p1 / p0 - 1) * 100, 2) if p0 > 0 else None
    except Exception:
        return None


def fill_outcomes(last_n: int = 50) -> int:
    if not os.path.exists(SIGNAL_FILE):
        return 0
    lines = []
    with open(SIGNAL_FILE) as fh:
        for line in fh:
            if line.strip():
                lines.append(json.loads(line))
    updated = 0
    for rec in lines:
        if rec.get("outcomes", {}).get("ret_5d") is not None:
            continue
        d = (rec.get("scan_time") or rec.get("logged_at", ""))[:10]
        if not d:
            continue
        rec["outcomes"] = {
            "ret_1d": _fwd(rec["focus"], d, 1),
            "ret_5d": _fwd(rec["focus"], d, 5),
        }
        updated += 1
    if updated:
        with open(SIGNAL_FILE, "w") as fh:
            for rec in lines:
                fh.write(json.dumps(rec) + "\n")
    return updated


if __name__ == "__main__":
    n = fill_outcomes()
    print(f"Updated outcomes on {n} records → {SIGNAL_FILE}")
