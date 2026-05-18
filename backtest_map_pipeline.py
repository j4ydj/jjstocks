#!/usr/bin/env python3
"""
Thorough walk-forward backtest of map-based pipeline (predictions + P&L).

  python backtest_map_pipeline.py
  python backtest_map_pipeline.py --years 2 --step 3
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from correlation_map import _bulk_download, _returns_matrix
from momentum_chain import rank_by_volatility
from pipeline_core import (
    CORR_WINDOW,
    HOLD_DAYS,
    generate_predictions,
    simulate_prediction,
)

WARMUP = CORR_WINDOW + 30
REPORT_PATH = "BACKTEST_PIPELINE_RESULTS.md"
CSV_PATH = "data/BACKTEST_PIPELINE_TRADES.csv"


def _stats(rows: List[Dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0}
    rets = [r["return_pct"] for r in rows]
    dir_ok = [r["direction_correct"] for r in rows]
    return {
        "n": len(rows),
        "win_rate": round(100 * sum(1 for x in rets if x > 0) / len(rets), 1),
        "dir_accuracy": round(100 * sum(dir_ok) / len(dir_ok), 1),
        "avg_return": round(float(np.mean(rets)), 2),
        "median_return": round(float(np.median(rets)), 2),
        "total_return": round(float(np.sum(rets)), 2),
        "stop_rate": round(100 * sum(1 for r in rows if r.get("hit_stop")) / len(rows), 1),
    }


def write_report(
    results: List[Dict],
    meta: Dict,
    path: str = REPORT_PATH,
) -> None:
    s = _stats(results)
    by_type: Dict[str, List] = defaultdict(list)
    for r in results:
        by_type[r.get("prediction_type", "?")].append(r)

    lines = [
        "# Map pipeline backtest — validation results",
        "",
        f"> Generated: **{meta['generated']}**",
        f"> Period: **{meta['period']}** | Step: every **{meta['step']}** trading days",
        f"> Focus per signal: **{meta['focus_n']}** | Corr window: **{CORR_WINDOW}d**",
        "",
        "## Executive summary",
        "",
        "This backtests the **same engine** that powers the automated daily pipeline:",
        "multi-horizon correlations, chain paths, predicted move %, expected date, entry/stop/target.",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Simulated trades | {s['n']} |",
    ]
    if s["n"]:
        lines.extend([
            f"| Win rate (P&L) | **{s['win_rate']}%** |",
            f"| Direction prediction accuracy | **{s['dir_accuracy']}%** |",
            f"| Avg return / trade | **{s['avg_return']:+.2f}%** |",
            f"| Median return | **{s['median_return']:+.2f}%** |",
            f"| Sum of returns (not compounded) | {s['total_return']:+.2f}% |",
            f"| Stopped out | {s['stop_rate']}% |",
        ])

    lines.extend(["", "## By prediction type", ""])
    for t, rows in sorted(by_type.items()):
        st = _stats(rows)
        lines.append(
            f"- **{t}**: n={st['n']}, win={st['win_rate']}%, "
            f"dir_acc={st['dir_accuracy']}%, avg={st['avg_return']:+.2f}%"
        )

    lines.extend(["", "## Compare to older backtests", ""])
    lines.extend([
        "- `BACKTEST_SETUPS_2Y.csv` — narrow chain rules (~37% win)",
        "- `BACKTEST_SETUPS_ADAPTIVE.csv` — filtered narrow rules (~35% win)",
        "- **This file** — map-based pipeline with chain paths",
        "",
    ])

    lines.extend(["", "## Last 50 trades", ""])
    lines.append(
        "| Signal | Focus | Type | Dir | Leader | Predicted | Actual | Ret% | Dir OK |"
    )
    lines.append("|--------|-------|------|-----|--------|-----------|--------|------|--------|")
    for r in sorted(results, key=lambda x: x["signal_date"])[-50:]:
        lines.append(
            f"| {r['signal_date']} | {r['focus']} | {r['prediction_type']} | {r['direction']} | "
            f"{r['leader']} | {r['predicted_move_pct']:+.1f}% | {r.get('actual_move_pct', 0):+.1f}% | "
            f"{r['return_pct']:+.1f}% | {'✓' if r.get('direction_correct') else '✗'} |"
        )

    lines.extend([
        "",
        f"## Full trade log",
        "",
        f"`{CSV_PATH}`",
        "",
        "```bash",
        "python backtest_map_pipeline.py --years 2",
        "```",
        "",
    ])
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def run_backtest(years: int = 2, step: int = 3, focus_n: int = 12, universe_cap: int = 280) -> List[Dict]:
    from universe import load_scan_universe

    tickers = load_scan_universe()[:universe_cap]
    from momentum_chain import MACRO_NODES

    for m in MACRO_NODES:
        if m not in tickers:
            tickers.append(m)

    print(f"Downloading {len(tickers)} symbols ({years}y)...")
    data = _bulk_download(tickers, period=f"{years}y")
    rets = _returns_matrix(data, min_bars=WARMUP + HOLD_DAYS + 10)
    print(f"Matrix: {len(rets)} days × {len(rets.columns)} symbols")

    results: List[Dict] = []
    dates = rets.index

    for i in range(WARMUP, len(dates) - HOLD_DAYS - 2, step):
        signal_date = str(dates[i])[:10]
        # rolling focus by vol
        vol_picks = []
        scores = []
        for sym in rets.columns:
            if sym not in data or sym in MACRO_NODES:
                continue
            sub = data[sym]["Close"].iloc[max(0, i - 15) : i + 1]
            if len(sub) < 6:
                continue
            r1 = (sub.iloc[-1] / sub.iloc[-2] - 1) * 100 if len(sub) >= 2 else 0
            vol = sub.pct_change(fill_method=None).std() * np.sqrt(252) * 100
            scores.append((sym, abs(r1) * 0.6 + vol * 0.4))
        scores.sort(key=lambda x: x[1], reverse=True)
        focus_list = [s[0] for s in scores[:focus_n]]

        movers, preds = generate_predictions(data, rets, focus_list, signal_date, end_idx=i)
        for p in preds[:8]:
            sim = simulate_prediction(data, p, i)
            if not sim:
                continue
            row = {**p.to_trade_dict(), **sim}
            results.append(row)

        if (len(results) % 50) < 8:
            print(f"  {signal_date}: {len(preds)} preds, {len(results)} trades total")

    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=2)
    p.add_argument("--step", type=int, default=3)
    p.add_argument("--focus", type=int, default=12)
    args = p.parse_args()

    results = run_backtest(args.years, args.step, args.focus)
    os.makedirs(os.path.dirname(CSV_PATH) or ".", exist_ok=True)
    if results:
        keys = list(results[0].keys())
        with open(CSV_PATH, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)

    meta = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period": f"{args.years}y",
        "step": args.step,
        "focus_n": args.focus,
    }
    write_report(results, meta)
    s = _stats(results)
    print(f"Done: {s['n']} trades → {REPORT_PATH}")
    if s["n"]:
        print(f"  Win {s['win_rate']}% | Dir acc {s['dir_accuracy']}% | Avg {s['avg_return']:+.2f}%")


if __name__ == "__main__":
    main()
