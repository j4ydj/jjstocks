#!/usr/bin/env python3
"""Compare unfiltered vs adaptive-filtered backtest results."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from setup_learning import passes_trade_row, rebuild_scores


def _stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    return {
        "n": len(df),
        "win_rate": round(100 * df["win"].mean(), 1),
        "avg": round(float(df["return_pct"].mean()), 2),
        "median": round(float(df["return_pct"].median()), 2),
        "stop_pct": round(100 * df["hit_stop"].astype(str).str.lower().eq("true").mean(), 1),
    }


def main() -> None:
    raw_path = "data/BACKTEST_SETUPS_2Y.csv"
    if not os.path.exists(raw_path):
        raw_path = "data/BACKTEST_SETUPS.csv"
    raw = pd.read_csv(raw_path)
    raw["win"] = raw["win"].astype(bool)

    scores = rebuild_scores()
    mask = []
    reasons = []
    for _, r in raw.iterrows():
        ok, why = passes_trade_row(
            r["setup_type"], r["direction"], int(r["lag"]), r["focus"], r["leader"], scores
        )
        mask.append(ok)
        if not ok:
            reasons.append(why)

    filt = raw[mask]
    s0, s1 = _stats(raw), _stats(filt)

    lines = [
        "# Backtest: before vs after adaptive filters",
        "",
        f"> Generated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**",
        f"> Source: `{raw_path}` filtered with `setup_learning` rules",
        "",
        "## Filters applied",
        "",
        "```json",
        str(scores.get("rules", {})),
        "```",
        "",
        f"Blocked pairs: **{len(scores.get('blocked_pairs', []))}**",
        "",
        "## Headline comparison",
        "",
        "| Metric | Before (all rules) | After (adaptive) |",
        "|--------|-------------------|------------------|",
        f"| Trades | {s0['n']} | {s1['n']} |",
    ]
    if s0["n"]:
        lines.append(f"| Win rate | {s0['win_rate']}% | {s1.get('win_rate', '—')}% |")
        lines.append(f"| Avg return | {s0['avg']:+.2f}% | {s1.get('avg', '—')}% |")
        lines.append(f"| Median return | {s0['median']:+.2f}% | {s1.get('median', '—')}% |")
        lines.append(f"| Stop rate | {s0['stop_pct']}% | {s1.get('stop_pct', '—')}% |")

    lines.extend(["", "## After filters — by setup type", ""])
    if not filt.empty:
        for st, g in filt.groupby("setup_type"):
            s = _stats(g)
            lines.append(f"- **{st}**: n={s['n']}, win={s['win_rate']}%, avg={s['avg']:+.2f}%")
    else:
        lines.append("_No trades pass when filtering lag=0 rows from old backtest._")
        lines.append("")
        lines.append("Run fresh adaptive backtest: `python backtest_setups.py --years 2 --adaptive`")

    lines.extend(["", "## Block reasons (from filtering old CSV)", ""])
    from collections import Counter
    c = Counter(reasons)
    for reason, n in c.most_common():
        lines.append(f"- {reason}: {n}")

    out = "BACKTEST_ADAPTIVE_COMPARE.md"
    with open(out, "w") as fh:
        fh.write("\n".join(lines))
    print(f"Wrote {out}")
    print(f"Before: n={s0['n']} win={s0.get('win_rate')}% avg={s0.get('avg')}%")
    print(f"After (filter CSV): n={s1['n']} win={s1.get('win_rate', 'n/a')}% avg={s1.get('avg', 'n/a')}%")


if __name__ == "__main__":
    main()
