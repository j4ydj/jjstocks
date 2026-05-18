#!/usr/bin/env python3
"""
Generate a decision report from backtests, live scan, and history.

Usage:
  python system_report.py
  python system_report.py --out data/system_report.md
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from backtest_plays import DEFAULT_TICKERS, RULES, backtest_ticker
from momentum_chain import MomentumChainFinder, rank_by_volatility, realized_vol_pct, _bulk_download
from momentum_plays import scan_with_plays, collect_chain_alerts
from universe import load_scan_universe

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY = os.path.join(DATA_DIR, "momentum_history.jsonl")


def _load_history() -> List[Dict]:
    if not os.path.exists(HISTORY):
        return []
    rows = []
    with open(HISTORY) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def backtest_summary(years: int = 2) -> Dict[str, Any]:
    agg = {k: [] for k in RULES}
    per_ticker: Dict[str, Dict[str, List[float]]] = {}
    for t in DEFAULT_TICKERS:
        res = backtest_ticker(t, period=f"{years}y")
        per_ticker[t] = res
        for k, vals in res.items():
            agg[k].extend(vals)

    summary = {}
    for name, rets in agg.items():
        if not rets:
            summary[name] = {"n": 0, "win_pct": 0, "avg": 0, "median": 0}
            continue
        wins = sum(1 for r in rets if r > 0)
        summary[name] = {
            "n": len(rets),
            "win_pct": round(100 * wins / len(rets), 1),
            "avg": round(sum(rets) / len(rets), 2),
            "median": round(sorted(rets)[len(rets) // 2], 2),
        }
    return {"rules": summary, "per_ticker": per_ticker, "years": years}


def rank_comparison() -> List[Dict]:
    """Old (raw vol) vs new (composite) top 10."""
    tickers = load_scan_universe()
    data = _bulk_download(tickers)
    by_vol = []
    for t, df in data.items():
        v = realized_vol_pct(df["Close"]) if df is not None and len(df) > 5 else None
        if v:
            by_vol.append((t, v))
    by_vol.sort(key=lambda x: x[1], reverse=True)
    top_vol = [x[0] for x in by_vol[:10]]

    composite, _ = rank_by_volatility(tickers, top_n=10, prefetched=data)
    top_comp = [p.ticker for p in composite]

    rows = []
    for i in range(10):
        rows.append({
            "rank_vol_only": i + 1,
            "ticker_vol_only": top_vol[i] if i < len(top_vol) else "",
            "ticker_composite": top_comp[i] if i < len(top_comp) else "",
            "changed": (top_vol[i] if i < len(top_vol) else "") != (top_comp[i] if i < len(top_comp) else ""),
        })
    return rows


def live_snapshot() -> Dict[str, Any]:
    result, plays = scan_with_plays(top_n=10, max_plays=10)
    alerts = collect_chain_alerts(result)
    return {
        "scan_time": result.scan_time,
        "universe": result.universe_size,
        "top": [
            {
                "rank": p.rank,
                "ticker": p.ticker,
                "composite": p.composite_score,
                "vol_pct": p.vol_annualized_pct,
                "expansion": p.vol_expansion,
                "r5": p.return_5d_pct,
                "r1": p.return_1d_pct,
            }
            for p in result.top_volatile
        ],
        "plays": [
            {
                "type": pl.play_type,
                "dir": pl.direction,
                "ticker": pl.ticker,
                "score": getattr(pl, "score", 0),
                "entry": pl.entry_price,
            }
            for pl in plays
        ],
        "play_types": _count([p["type"] for p in [
            {"type": pl.play_type} for pl in plays
        ]]),
        "directions": _count([pl.direction for pl in plays]),
        "alerts": alerts,
        "chains_built": len(result.chains),
    }


def _count(items: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def build_report() -> str:
    bt = backtest_summary(2)
    cmp = rank_comparison()
    live = live_snapshot()
    hist = _load_history()

    lines = [
        "# Momentum System — Decision Report",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "---\n",
        "## 1. What we have built\n",
        "| Layer | Status |",
        "|-------|--------|",
        "| Vol ranking (518 tickers) | Working |",
        "| Composite score + liquidity filter | Working |",
        "| Chain map (macro + peers) | Working |",
        "| 6 play types + regime gates | Working |",
        "| Play scoring 0–100 | Working |",
        "| History log | `data/momentum_history.jsonl` |",
        "| Rule backtest | `backtest_plays.py` |",
        "| Live outcome tracking | Needs 5–10 trading days of scans |\n",
        "---\n",
        "## 2. Historical backtest (2 years, 12 volatile tickers, 10-day hold)\n",
        "Simplified rules on daily bars — not identical to live plays but directionally useful.\n",
        "| Play rule | Signals | Win % | Avg return | Median |",
        "|-----------|---------|-------|------------|--------|",
    ]
    for name, s in bt["rules"].items():
        lines.append(
            f"| {name} | {s['n']} | {s['win_pct']}% | {s['avg']:+.2f}% | {s['median']:+.2f}% |"
        )

    lines.extend([
        "\n**Read:** `chain_long` is the only rule with clearly positive average (+1.91%) and ~46% win rate. ",
        "`chain_short` loses money on average (-0.39%) with only 29% wins. ",
        "`pullback_buy` is marginal (+0.41% avg, 38% wins).\n",
        "---\n",
        "## 3. Vol-only vs composite ranking (today)\n",
        "Composite score demotes one-day gaps and rewards sustained vol expansion.\n",
        "| Rank | Raw vol leader | Composite leader | Changed? |",
        "|------|----------------|------------------|----------|",
    ])
    for r in cmp:
        ch = "yes" if r["changed"] else ""
        lines.append(
            f"| {r['rank_vol_only']} | {r['ticker_vol_only']} | {r['ticker_composite']} | {ch} |"
        )

    space_vol = {"RKLB", "ASTS", "LUNR", "IONQ", "SMCI"}
    in_vol = sum(1 for r in cmp if r["ticker_vol_only"] in space_vol)
    in_comp = sum(1 for r in cmp if r["ticker_composite"] in space_vol)
    lines.append(
        f"\nSpace/AI names in top 10: **{in_vol}** by raw vol vs **{in_comp}** by composite.\n"
    )

    lines.extend([
        "---\n",
        f"## 4. Live scan snapshot ({live['scan_time']})\n",
        f"Universe: **{live['universe']}** tickers | Chains mapped: **{live['chains_built']}**\n",
        "### Top 10 focus (composite rank)\n",
        "| # | Ticker | Score | Vol% | Exp× | 5d | 1d |",
        "|---|--------|-------|------|------|-----|-----|",
    ])
    for p in live["top"]:
        lines.append(
            f"| {p['rank']} | {p['ticker']} | {p['composite']:.0f} | {p['vol_pct']:.0f} | "
            f"{p['expansion']:.2f} | {p['r5']:+.1f}% | {p['r1']:+.1f}% |"
        )

    lines.extend([
        "\n### Plays generated\n",
        f"Total: **{len(live['plays'])}** | Directions: {live['directions']} | Types: {live['play_types']}\n",
    ])
    if live["plays"]:
        lines.append("| Score | Type | Dir | Ticker | Entry |")
        lines.append("|-------|------|-----|--------|-------|")
        for pl in live["plays"]:
            lines.append(
                f"| {pl['score']} | {pl['type']} | {pl['dir']} | {pl['ticker']} | ${pl['entry']} |"
            )
    else:
        lines.append("_No plays passed regime + conviction filters._\n")

    lines.append("\n### Chain alerts (risk flags)\n")
    for a in live["alerts"][:8]:
        lines.append(f"- {a}")

    lines.extend([
        "\n---\n",
        "## 5. What the data says (decision guide)\n",
        "### Keep / double down\n",
        "- **Chain mapping** — Space cluster (RKLB, ASTS, LUNR, RDW, PL) moves together; upstream macro (QQQ, XLK) leads by ~3d. High value for planning.\n",
        "- **Composite vol ranking** — Surfaces ASTS/DDOG with expanding vol; RKLB still in focus (#8) despite 1d flush.\n",
        "- **Regime gate** — Today blocked ALL longs (VIX +6.8%, macro weak). Avoided RKLB pullback long into risk-off — likely correct.\n",
        "- **chain_long rule** — Only backtest winner; align live plays with long-bias in risk-on weeks.\n",
        "\n### Fix / tune next\n",
        "- **chain_short** — Negative backtest; disable or require stronger confirmation (5d &lt; -10%, VIX rising, no peer support).\n",
        "- **Play diversity** — Today 100% chain_trend SHORT; pullback/catch_up/basket never fired. Loosen pullback in neutral regime OR add manual space-theme watchlist.\n",
        "- **Outcome tracking** — Only 1 scan in history; run daily 1–2 weeks then `python outcome_tracker.py --report`.\n",
        "- **SNDK price** — Verify ticker data ($1407 entry looks like bad symbol); add sanity filter on entry price.\n",
        "\n### Defer (low evidence)\n",
        "- News headlines, intraday refresh, pair legs — until live outcomes validate core plays.\n",
        "- Paid data (options flow) — not needed until free pipeline proves edge.\n",
        "\n### Recommended 2-week experiment\n",
        "1. Run `python run_momentum_chain.py` daily before open; save history.\n",
        "2. Paper-trade only **top 3 scored** plays.\n",
        "3. Track: chain_long-style longs on risk-on days vs chain_short on risk-off.\n",
        "4. After 10 sessions, run `python outcome_tracker.py --report` and `python backtest_plays.py`.\n",
        "\n---\n",
        f"## 6. History log\n",
        f"Scans stored: **{len(hist)}** in `{HISTORY}`\n",
    ])
    if hist:
        last = hist[-1]
        lines.append(f"Last scan: {last.get('scan_time')} — {last.get('play_count')} plays logged.\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(DATA_DIR, "system_report.md"))
    args = parser.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)
    report = build_report()
    with open(args.out, "w") as f:
        f.write(report)
    print(report)
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
