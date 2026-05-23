#!/usr/bin/env python3
"""
Tier 3: backtest / track approved-trade layer (paper + logged setups).

  python3 backtest_approved.py
  python3 backtest_approved.py --from-csv data/BACKTEST_PIPELINE_TRADES_V2.csv
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from typing import Any, Dict, List

import numpy as np

REPORT = "APPROVED_BACKTEST.md"


def _stats(rows: List[Dict[str, Any]], ret_key: str = "return_pct") -> Dict[str, Any]:
    if not rows:
        return {"n": 0, "win_rate": 0, "avg_return": 0}
    rets = [float(r[ret_key]) for r in rows if r.get(ret_key) is not None]
    if not rets:
        return {"n": 0, "win_rate": 0, "avg_return": 0}
    return {
        "n": len(rets),
        "win_rate": round(100 * sum(1 for x in rets if x > 0) / len(rets), 1),
        "avg_return": round(float(np.mean(rets)), 2),
        "median_return": round(float(np.median(rets)), 2),
    }


def _from_trade_setups() -> List[Dict[str, Any]]:
    from trade_tracker import load_all, _dedupe_trades

    rows = []
    for r in _dedupe_trades(load_all()):
        if r.get("pipeline") != "approved_v2":
            continue
        oc = r.get("outcomes") or {}
        ret = oc.get("ret_5d") or oc.get("ret_7d")
        if ret is None:
            continue
        rows.append({
            "ticker": r.get("ticker"),
            "direction": r.get("direction"),
            "return_pct": ret,
            "alt_score": r.get("alt_score"),
            "scan_time": r.get("scan_time"),
        })
    return rows


def _from_csv(path: str, min_corr: float = 0.60) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            try:
                corr = abs(float(row.get("corr") or 0))
            except ValueError:
                continue
            if corr < min_corr:
                continue
            try:
                ret = float(row.get("return_pct") or row.get("net_return_pct") or 0)
            except ValueError:
                continue
            out.append({**row, "return_pct": ret, "corr": corr})
    return out


def write_report(live: List[Dict], csv_rows: List[Dict], paper: Dict[str, Any]) -> str:
    s_live = _stats(live)
    s_csv = _stats(csv_rows)
    lines = [
        "# Approved layer backtest",
        "",
        f"> Generated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**",
        "",
        "## Live approved trades (5d/7d outcomes)",
        "",
        f"| Trades scored | {s_live['n']} |",
        f"| Win rate | {s_live.get('win_rate', 0)}% |",
        f"| Avg return | {s_live.get('avg_return', 0):+.2f}% |",
        "",
        "## Paper portfolio (compound, 2% risk sizing)",
        "",
        f"| Equity | ${paper.get('equity', 0):,.0f} |",
        f"| Total return | {paper.get('total_return_pct', 0):+.1f}% |",
        f"| Closed trades | {paper.get('trade_count', 0)} |",
        f"| Win rate | {paper.get('win_rate', 0)}% |",
        f"| Open now | {paper.get('open_positions', 0)} |",
        "",
    ]
    if s_csv["n"]:
        lines += [
            "## Proxy from pipeline v2 backtest CSV (|r|≥0.60)",
            "",
            f"| Trades | {s_csv['n']} |",
            f"| Win rate | {s_csv['win_rate']}% |",
            f"| Avg return | {s_csv['avg_return']:+.2f}% |",
            "",
            "_Run `python3 backtest_map_pipeline.py` to refresh CSV._",
        ]
    else:
        lines.append("_No backtest CSV — run `python3 backtest_map_pipeline.py --years 2`._")
    text = "\n".join(lines)
    with open(REPORT, "w") as fh:
        fh.write(text)
    return text


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from-csv", default="data/BACKTEST_PIPELINE_TRADES_V2.csv")
    args = p.parse_args()

    live = _from_trade_setups()
    csv_rows = _from_csv(args.from_csv)
    paper: Dict[str, Any] = {}
    try:
        from paper_portfolio import get_portfolio_summary

        paper = get_portfolio_summary()
    except Exception:
        pass

    text = write_report(live, csv_rows, paper)
    print(text)


if __name__ == "__main__":
    main()
