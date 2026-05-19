#!/usr/bin/env python3
"""
Backtest v2: strict signal filters → train pair playbook → out-of-sample test.

  python3 backtest_map_pipeline.py --years 2 --step 5
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from correlation_map import _bulk_download, _returns_matrix
from momentum_chain import MACRO_NODES
from pair_playbook import PairPlaybook, rebuild_from_csv
from pipeline_config import CORR_WINDOW, HOLD_DAYS, TARGET_WIN_RATE, WF_TRAIN_FRAC
from pipeline_core import ChainPrediction, generate_predictions, simulate_prediction
from pipeline_filters import select_portfolio

WARMUP = CORR_WINDOW + 30
REPORT_PATH = "BACKTEST_PIPELINE_RESULTS.md"
CSV_PATH = "data/BACKTEST_PIPELINE_TRADES.csv"
CSV_FILTERED = "data/BACKTEST_PIPELINE_TRADES_V2.csv"


def _stats(rows: List[Dict]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "win_rate": 0, "avg_return": 0, "median_return": 0, "stop_rate": 0}
    rets = [r["return_pct"] for r in rows]
    return {
        "n": len(rows),
        "win_rate": round(100 * sum(1 for x in rets if x > 0) / len(rets), 1),
        "avg_return": round(float(np.mean(rets)), 2),
        "median_return": round(float(np.median(rets)), 2),
        "stop_rate": round(100 * sum(1 for r in rows if r.get("hit_stop")) / len(rets), 1),
    }


def _build_playbook_adaptive(trades: List[Dict]) -> Dict[str, Any]:
    pb = PairPlaybook()
    for target in (TARGET_WIN_RATE, 85, 80, 75):
        pb.target_win_rate = target
        doc = pb.build_static_from_trades(trades)
        if doc["allowed_count"] >= 3:
            doc["target_win_rate_used"] = target
            return doc
    return pb.build_static_from_trades(trades)


def write_report(raw: List[Dict], filtered: List[Dict], meta: Dict, playbook: Dict) -> None:
    s_raw, s_f = _stats(raw), _stats(filtered)
    lines = [
        "# Map pipeline v2 backtest",
        "",
        f"> Generated: **{meta['generated']}**",
        f"> OOS period after train fraction **{WF_TRAIN_FRAC:.0%}**",
        f"> Playbook target: **{playbook.get('target_win_rate_used', TARGET_WIN_RATE)}%** "
        f"({playbook.get('allowed_count', 0)} pairs)",
        "",
        "## Out-of-sample (playbook + portfolio caps)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Trades | {s_f['n']} |",
    ]
    if s_f["n"]:
        lines += [
            f"| Win rate (net) | **{s_f['win_rate']}%** |",
            f"| Avg return | **{s_f['avg_return']:+.2f}%** |",
            f"| Median | **{s_f['median_return']:+.2f}%** |",
        ]
    lines += [
        "",
        f"## All candidates (signal filters only): {s_raw['n']} trades, {s_raw.get('win_rate', 0)}% win",
        "",
        "### Whitelisted pairs (train)",
    ]
    for row in playbook.get("allowed", [])[:15]:
        lines.append(
            f"- {row['focus']}/{row['leader']} {row['direction']} "
            f"({row['prediction_type']}): {row['win_rate']}% win, n={row['n']}"
        )
    lines += ["", f"Logs: `{CSV_FILTERED}`, `{CSV_PATH}`"]
    with open(REPORT_PATH, "w") as fh:
        fh.write("\n".join(lines))


def run_backtest(years: int = 2, step: int = 5, focus_n: int = 12, universe_cap: int = 280) -> Tuple:
    from universe import load_scan_universe

    tickers = load_scan_universe()[:universe_cap]
    for m in MACRO_NODES:
        if m not in tickers:
            tickers.append(m)

    print(f"Downloading {len(tickers)} symbols ({years}y)...")
    data = _bulk_download(tickers, period=f"{years}y")
    rets = _returns_matrix(data, min_bars=WARMUP + HOLD_DAYS + 10)
    dates = rets.index
    split_i = int(len(dates) * WF_TRAIN_FRAC)
    split_date = str(dates[split_i])[:10]
    print(f"Matrix: {len(rets)} days | Train until {split_date}")

    raw_all: List[Dict] = []
    oos_filtered: List[Dict] = []

    for i in range(WARMUP, len(dates) - HOLD_DAYS - 2, step):
        signal_date = str(dates[i])[:10]
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

        _, preds = generate_predictions(
            data, rets, focus_list, signal_date, end_idx=i, apply_playbook=False,
        )
        for p in preds:
            sim = simulate_prediction(data, p, i, rets=rets)
            if sim:
                raw_all.append({**p.to_trade_dict(), **sim})

    print(f"Raw candidates: {len(raw_all)}")
    train_rows = [r for r in raw_all if (r.get("signal_date") or "")[:10] < split_date]
    pb_doc = _build_playbook_adaptive(train_rows)
    pb = PairPlaybook(target_win_rate=pb_doc.get("target_win_rate_used", TARGET_WIN_RATE))
    pb.save(pb_doc)
    print(f"Playbook: {pb_doc['allowed_count']} pairs @ {pb_doc.get('target_win_rate_used')}% win")

    for i in range(WARMUP, len(dates) - HOLD_DAYS - 2, step):
        signal_date = str(dates[i])[:10]
        if signal_date < split_date:
            continue
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

        _, preds = generate_predictions(
            data, rets, focus_list, signal_date, end_idx=i, apply_playbook=False,
        )
        allowed: List[ChainPrediction] = []
        for p in preds:
            if pb._static_allowed:
                ok, _ = pb.allows_static(p.focus, p.leader, p.direction, p.prediction_type)
                if not ok:
                    continue
            allowed.append(p)
        chosen, _ = select_portfolio(allowed)
        for p in chosen:
            sim = simulate_prediction(data, p, i, rets=rets)
            if sim:
                oos_filtered.append({**p.to_trade_dict(), **sim})

    train_raw = [r for r in raw_all if (r.get("signal_date") or "")[:10] < split_date]
    oos_raw = [r for r in raw_all if (r.get("signal_date") or "")[:10] >= split_date]
    print(f"Train win: {_stats(train_raw).get('win_rate', 0)}% | OOS raw: {_stats(oos_raw).get('win_rate', 0)}%")
    return raw_all, oos_filtered, pb_doc


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=2)
    p.add_argument("--step", type=int, default=5)
    p.add_argument("--focus", type=int, default=12)
    args = p.parse_args()

    raw, filtered, pb_doc = run_backtest(args.years, args.step, args.focus)
    os.makedirs("data", exist_ok=True)
    if raw:
        with open(CSV_PATH, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(raw[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(raw)
    if filtered:
        with open(CSV_FILTERED, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(filtered[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(filtered)
    rebuild_from_csv(CSV_FILTERED if filtered else CSV_PATH)

    meta = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    write_report(raw, filtered, meta, pb_doc)
    s = _stats(filtered)
    print(f"OOS filtered: {s['n']} trades, win {s.get('win_rate', 0)}%, avg {s.get('avg_return', 0):+.2f}%")


if __name__ == "__main__":
    main()
