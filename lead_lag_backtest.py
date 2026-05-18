#!/usr/bin/env python3
"""
Lead/lag forward validation — full export for verification.

  python lead_lag_backtest.py
  python lead_lag_backtest.py --out data/BACKTEST_LEAD_LAG.csv
  python lead_lag_backtest.py --focus RKLB,DDOG --period 1y
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from chain_stats import corr_pvalue, corr_significant, lead_lag_hit_rate
from momentum_chain import (
    CORR_LOOKBACK_DAYS,
    MACRO_NODES,
    MIN_CORR_ABS,
    THEMATIC_LINKS,
    _candidate_nodes,
    daily_returns,
    lead_lag_corr,
)

DEFAULT_FOCUS = [
    "RKLB", "AKAM", "JOBY", "DDOG", "ZTS", "SMCI", "ASTS", "LUNR",
    "PLTR", "NVDA", "AMD", "COIN", "MSTR", "IONQ", "GME", "HOOD", "SOFI",
]
OOS_TEST_DAYS = int(os.getenv("LAG_OOS_TEST_DAYS", "40"))


def _close_series(ticker: str, period: str) -> Optional[pd.Series]:
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        s = df["Close"].squeeze()
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s.dropna()
    except Exception:
        return None


def _nodes_for_focus(focus: str) -> List[str]:
    nodes = set(MACRO_NODES.keys())
    for sym, _, _ in _candidate_nodes(focus):
        nodes.add(sym)
    thematic = THEMATIC_LINKS.get(focus.upper(), {})
    for key in ("upstream_macro", "upstream_micro", "downstream_micro"):
        nodes.update(thematic.get(key, []))
    nodes.discard(focus.upper())
    return sorted(nodes)


def _oos_hit(
    fr: pd.Series,
    nr: pd.Series,
    lag: int,
    corr: float,
    test_days: int = OOS_TEST_DAYS,
) -> Tuple[Optional[float], int]:
    """Hit rate on the most recent test_days not used for lag selection."""
    if len(fr) < CORR_LOOKBACK_DAYS + test_days + 5:
        return None, 0
    train_fr = fr.iloc[:-test_days].tail(CORR_LOOKBACK_DAYS)
    train_nr = nr.reindex(train_fr.index).dropna()
    train_fr = train_fr.reindex(train_nr.index).dropna()
    test_fr = fr.iloc[-test_days:]
    test_nr = nr.reindex(test_fr.index).dropna()
    test_fr = test_fr.reindex(test_nr.index).dropna()
    if len(test_fr) < 10:
        return None, 0
    return lead_lag_hit_rate(test_fr, test_nr, lag, corr, min_events=5)


def evaluate_pair(
    focus: str,
    node: str,
    period: str,
) -> Optional[Dict[str, Any]]:
    f_close = _close_series(focus, period)
    n_close = _close_series(node, period)
    if f_close is None or n_close is None:
        return None

    fr = daily_returns(f_close)
    nr = daily_returns(n_close)
    aligned = pd.concat([fr, nr], axis=1, join="inner").dropna()
    if len(aligned) < CORR_LOOKBACK_DAYS + 10:
        return None
    fr = aligned.iloc[:, 0]
    nr = aligned.iloc[:, 1]
    n = len(fr.tail(CORR_LOOKBACK_DAYS))
    train_fr = fr.tail(CORR_LOOKBACK_DAYS)
    train_nr = nr.tail(CORR_LOOKBACK_DAYS)

    corr, lag = lead_lag_corr(train_fr, train_nr)
    pval = corr_pvalue(corr, n)
    hit, hit_n = lead_lag_hit_rate(train_fr, train_nr, lag, corr, min_events=5)
    oos_hit, oos_n = _oos_hit(fr, nr, lag, corr)

    if lag > 0:
        lag_label = f"node leads {focus} ~{lag}d"
    elif lag < 0:
        lag_label = f"node lags {focus} ~{-lag}d"
    else:
        lag_label = "same day"

    layer = "macro" if node in MACRO_NODES else "micro"
    passes = abs(corr) >= MIN_CORR_ABS and (n < 20 or pval <= 0.05)

    return {
        "focus": focus,
        "node": node,
        "layer": layer,
        "period": period,
        "lookback_days": CORR_LOOKBACK_DAYS,
        "sample_n": n,
        "corr": round(corr, 4),
        "pvalue": round(pval, 6),
        "significant": corr_significant(corr, n),
        "passes_alert_filter": passes,
        "lag_days": lag,
        "lag_label": lag_label,
        "hit_rate_insample_pct": hit,
        "hit_events_insample": hit_n,
        "hit_rate_oos_pct": oos_hit,
        "hit_events_oos": oos_n,
        "data_start": str(fr.index.min())[:10],
        "data_end": str(fr.index.max())[:10],
    }


def run_backtest(
    focus_list: List[str],
    period: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for focus in focus_list:
        for node in _nodes_for_focus(focus):
            row = evaluate_pair(focus, node, period)
            if row:
                rows.append(row)
    return rows


def write_csv(rows: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_markdown(rows: List[Dict[str, Any]], path: str, meta: Dict[str, Any]) -> None:
    lines = [
        "# Lead/lag backtest — full results",
        "",
        f"> Generated: **{meta['generated']}**",
        f"> Period: **{meta['period']}** | Corr lookback: **{meta['lookback']}d** | "
        f"OOS test window: **{meta['oos_days']}d** (most recent days)",
        f"> Alert filter: |r| ≥ **{meta['min_corr']}**, p < 0.05 when n≥20",
        f"> Focus tickers: {meta['focus_count']} | Total pairs tested: **{len(rows)}**",
        "",
        "## Summary",
        "",
    ]
    passing = [r for r in rows if r["passes_alert_filter"]]
    with_hit = [r for r in passing if r["hit_rate_insample_pct"] is not None]
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Pairs tested | {len(rows)} |")
    lines.append(f"| Pass alert filter | {len(passing)} |")
    if with_hit:
        avg_hit = sum(r["hit_rate_insample_pct"] for r in with_hit) / len(with_hit)
        lines.append(f"| Avg in-sample hit (filtered) | {avg_hit:.1f}% |")
    oos_pass = [r for r in passing if r["hit_rate_oos_pct"] is not None]
    if oos_pass:
        avg_oos = sum(r["hit_rate_oos_pct"] for r in oos_pass) / len(oos_pass)
        lines.append(f"| Avg OOS hit (filtered) | {avg_oos:.1f}% |")
    lines.extend(["", "## All pairs (sorted by focus, then |corr|)", ""])
    lines.append(
        "| focus | node | layer | corr | pvalue | lag | in-sample hit | n | OOS hit | OOS n | passes |"
    )
    lines.append(
        "|-------|------|-------|------|--------|-----|---------------|---|---------|-------|--------|"
    )

    sorted_rows = sorted(rows, key=lambda r: (r["focus"], -abs(r["corr"])))
    for r in sorted_rows:
        ins = f"{r['hit_rate_insample_pct']:.1f}%" if r["hit_rate_insample_pct"] is not None else "—"
        oos = f"{r['hit_rate_oos_pct']:.1f}%" if r["hit_rate_oos_pct"] is not None else "—"
        lines.append(
            f"| {r['focus']} | {r['node']} | {r['layer']} | {r['corr']:+.3f} | {r['pvalue']:.4f} | "
            f"{r['lag_days']:+d} | {ins} | {r['hit_events_insample']} | {oos} | {r['hit_events_oos']} | "
            f"{'yes' if r['passes_alert_filter'] else 'no'} |"
        )

    lines.extend([
        "",
        "## Pairs that pass alert filter (would appear in Telegram)",
        "",
        "| focus | node | corr | lag | in-sample hit | OOS hit | lag_label |",
        "|-------|------|------|-----|---------------|---------|-----------|",
    ])
    for r in sorted(passing, key=lambda x: (-(x["hit_rate_insample_pct"] or 0), -abs(x["corr"]))):
        ins = f"{r['hit_rate_insample_pct']:.1f}%" if r["hit_rate_insample_pct"] is not None else "—"
        oos = f"{r['hit_rate_oos_pct']:.1f}%" if r["hit_rate_oos_pct"] is not None else "—"
        lines.append(
            f"| {r['focus']} | {r['node']} | {r['corr']:+.3f} | {r['lag_days']:+d} | {ins} | {oos} | {r['lag_label']} |"
        )

    lines.extend([
        "",
        "## CSV",
        "",
        f"Machine-readable copy: `{meta['csv_path']}`",
        "",
        "## How to reproduce",
        "",
        "```bash",
        f"python lead_lag_backtest.py --period {meta['period']}",
        "```",
        "",
    ])
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--focus", default=",".join(DEFAULT_FOCUS))
    p.add_argument("--period", default="6mo", help="yfinance period (6mo, 1y, 2y)")
    p.add_argument("--out", default="data/BACKTEST_LEAD_LAG.csv")
    p.add_argument("--md", default="BACKTEST_LEAD_LAG.md")
    args = p.parse_args()
    focus_list = [t.strip().upper() for t in args.focus.split(",") if t.strip()]

    print(f"Running lead/lag backtest: {len(focus_list)} focus tickers, period={args.period}...")
    rows = run_backtest(focus_list, args.period)
    write_csv(rows, args.out)

    meta = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period": args.period,
        "lookback": CORR_LOOKBACK_DAYS,
        "oos_days": OOS_TEST_DAYS,
        "min_corr": MIN_CORR_ABS,
        "focus_count": len(focus_list),
        "csv_path": args.out,
    }
    write_markdown(rows, args.md, meta)
    passing = sum(1 for r in rows if r["passes_alert_filter"])
    print(f"Done: {len(rows)} pairs, {passing} pass filter")
    print(f"  CSV: {args.out}")
    print(f"  MD:  {args.md}")


if __name__ == "__main__":
    main()
