#!/usr/bin/env python3
"""
P&L backtest of live setup rules (catch_up, divergence, fade_risk).

Simulates what the actionable system would have proposed on historical days,
with ATR-based stops/targets and 5-day max hold.

  python backtest_setups.py
  python backtest_setups.py --years 2 --out BACKTEST_SETUPS.md
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from chain_setups import (
    CATCHUP_GAP_MIN,
    DIVERGE_MOVE_MIN,
    LEADER_MOVE_MIN,
    MACRO_DOWN_BLOCK,
    MIN_CORR_ABS,
    MIN_HIT_EVENTS,
    MIN_OOS_HIT,
    VIX_SPIKE_MAX,
)
from chain_stats import lead_lag_hit_rate, oos_hit_rate
from momentum_chain import (
    CORR_LOOKBACK_DAYS,
    MACRO_NODES,
    THEMATIC_LINKS,
    daily_returns,
    lead_lag_corr,
)
from trade_levels import calculate_levels

DEFAULT_FOCUS = [
    "RKLB", "ASTS", "LUNR", "SMCI", "PLTR", "NVDA", "AMD", "COIN", "MSTR",
    "IONQ", "GME", "JOBY", "DDOG", "HOOD", "SOFI",
]
HOLD_DAYS = int(os.getenv("SETUP_HOLD_DAYS", "5"))
WARMUP = CORR_LOOKBACK_DAYS + 45


@dataclass
class SimTrade:
    date: str
    setup_type: str
    focus: str
    leader: str
    direction: str
    corr: float
    lag: int
    leader_move: float
    focus_move: float
    entry: float
    exit: float
    return_pct: float
    hold_days: int
    hit_stop: bool
    hit_target: bool
    win: bool


def _download(symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            df = yf.download(sym, period=period, progress=False, auto_adjust=True)
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df = df.droplevel(1, axis=1)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if len(df) > WARMUP:
                out[sym] = df
        except Exception:
            continue
    return out


def _nodes_for(focus: str) -> List[str]:
    nodes = set(MACRO_NODES.keys())
    th = THEMATIC_LINKS.get(focus.upper(), {})
    for k in ("upstream_macro", "upstream_micro", "downstream_micro"):
        nodes.update(th.get(k, []))
    return sorted(nodes - {focus.upper()})


def _pct_move(close: pd.Series, i: int) -> float:
    if i < 1:
        return 0.0
    p0, p1 = float(close.iloc[i - 1]), float(close.iloc[i])
    return (p1 / p0 - 1) * 100 if p0 > 0 else 0.0


def _regime_ok(macro_moves: Dict[str, float], direction: str) -> bool:
    vix = macro_moves.get("^VIX", 0.0)
    spy = macro_moves.get("SPY", 0.0)
    qqq = macro_moves.get("QQQ", 0.0)
    if direction == "BUY":
        if vix > VIX_SPIKE_MAX:
            return False
        if spy < -MACRO_DOWN_BLOCK and qqq < -MACRO_DOWN_BLOCK:
            return False
    return True


def _simulate(
    focus_df: pd.DataFrame,
    entry_idx: int,
    direction: str,
) -> Optional[Dict[str, Any]]:
    if entry_idx + 1 >= len(focus_df):
        return None
    hist = focus_df.iloc[: entry_idx + 1]
    lv = calculate_levels("X", direction, hist, conviction=4, hold_days=HOLD_DAYS)
    if not lv:
        return None
    entry = float(focus_df["Open"].iloc[entry_idx + 1])
    risk = abs(lv.entry_price - lv.stop_loss)
    reward = abs(lv.target_price - lv.entry_price)
    if direction == "BUY":
        stop = entry - risk
        target = entry + reward
    else:
        stop = entry + risk
        target = entry - reward

    exit_idx = min(len(focus_df) - 1, entry_idx + 1 + HOLD_DAYS)
    exit_price = float(focus_df["Close"].iloc[exit_idx])
    hit_stop = hit_target = False

    for j in range(entry_idx + 1, exit_idx + 1):
        hi = float(focus_df["High"].iloc[j])
        lo = float(focus_df["Low"].iloc[j])
        if direction == "BUY":
            if lo <= stop:
                exit_price, hit_stop, exit_idx = stop, True, j
                break
            if hi >= target:
                exit_price, hit_target, exit_idx = target, True, j
                break
        else:
            if hi >= stop:
                exit_price, hit_stop, exit_idx = stop, True, j
                break
            if lo <= target:
                exit_price, hit_target, exit_idx = target, True, j
                break

    if direction == "BUY":
        ret = (exit_price / entry - 1) * 100
    else:
        ret = (entry / exit_price - 1) * 100 if exit_price > 0 else 0

    return {
        "entry": round(entry, 2),
        "exit": round(exit_price, 2),
        "return_pct": round(ret, 2),
        "hold_days": exit_idx - entry_idx,
        "hit_stop": hit_stop,
        "hit_target": hit_target,
    }


def backtest_pair(
    focus: str,
    leader: str,
    data: Dict[str, pd.DataFrame],
) -> List[SimTrade]:
    fdf = data.get(focus)
    ldf = data.get(leader)
    if fdf is None or ldf is None:
        return []

    idx = fdf.index.intersection(ldf.index)
    if len(idx) < WARMUP + HOLD_DAYS + 5:
        return []
    fdf = fdf.loc[idx]
    ldf = ldf.loc[idx]
    fr = daily_returns(fdf["Close"])
    nr = daily_returns(ldf["Close"])

    trades: List[SimTrade] = []
    macro_syms = ["SPY", "QQQ", "^VIX"]

    for i in range(WARMUP, len(fdf) - HOLD_DAYS - 2):
        train_fr = fr.iloc[i - CORR_LOOKBACK_DAYS : i]
        train_nr = nr.reindex(train_fr.index).dropna()
        train_fr = train_fr.reindex(train_nr.index).dropna()
        if len(train_fr) < CORR_LOOKBACK_DAYS - 5:
            continue

        corr, lag = lead_lag_corr(train_fr, train_nr)
        if abs(corr) < MIN_CORR_ABS:
            continue

        hit, hit_n = oos_hit_rate(fr.iloc[:i], nr.iloc[:i], lag, corr, min_events=MIN_HIT_EVENTS)
        if hit is None:
            hit, hit_n = lead_lag_hit_rate(train_fr, train_nr, lag, corr, min_events=MIN_HIT_EVENTS)
        if hit is None or hit < MIN_OOS_HIT or hit_n < MIN_HIT_EVENTS:
            continue

        f_move = _pct_move(fdf["Close"], i)
        l_move = _pct_move(ldf["Close"], i)
        if abs(l_move) < 0.01 and abs(f_move) < 0.01:
            continue

        macro_moves = {}
        for ms in macro_syms:
            mdf = data.get(ms)
            if mdf is None:
                continue
            try:
                aligned = mdf.reindex(idx).ffill()
                if i < len(aligned) and pd.notna(aligned["Close"].iloc[i]):
                    macro_moves[ms] = _pct_move(aligned["Close"], i)
            except Exception:
                pass

        date_s = str(idx[i])[:10]
        layer = "macro" if leader in MACRO_NODES else "micro"

        # --- catch_up ---
        use_prior_day = os.getenv("REQUIRE_LEADER_PRIOR_DAY", "0") == "1"
        if use_prior_day and i >= 2:
            l_move_signal = _pct_move(ldf["Close"], i - 1)
            f_move_signal = f_move
        else:
            l_move_signal = l_move
            f_move_signal = f_move

        catch_ok = (
            abs(l_move_signal) >= LEADER_MOVE_MIN
            and abs(f_move_signal) < abs(l_move_signal) - CATCHUP_GAP_MIN
        )

        if catch_ok and (lag >= 0 or layer == "micro"):
            if corr > 0:
                direction = "BUY" if l_move_signal > 0 else "SHORT"
            else:
                direction = "SHORT" if l_move_signal > 0 else "BUY"
            if os.getenv("DISABLE_BUY_CATCHUP", "0") == "1" and direction == "BUY":
                pass
            elif not _regime_ok(macro_moves, direction):
                pass
            else:
                pair = f"{focus}/{leader}"
                blocked = False
                try:
                    from setup_learning import load_scores
                    blocked = pair in load_scores().get("blocked_pairs", [])
                except Exception:
                    pass
                if not blocked:
                    sim = _simulate(fdf, i, direction)
                    if sim:
                        trades.append(
                            SimTrade(
                                date=date_s,
                                setup_type="catch_up",
                                focus=focus,
                                leader=leader,
                                direction=direction,
                                corr=round(corr, 3),
                                lag=lag,
                                leader_move=round(l_move_signal, 2),
                                focus_move=round(f_move_signal, 2),
                                win=sim["return_pct"] > 0,
                                **sim,
                            )
                        )

        # --- divergence (micro, positive corr) ---
        if os.getenv("DISABLE_DIVERGENCE", "0") == "1":
            pass
        elif layer == "micro" and corr > MIN_CORR_ABS:
            if f_move * l_move < 0 and abs(f_move) >= DIVERGE_MOVE_MIN and abs(l_move) >= DIVERGE_MOVE_MIN:
                direction = "BUY" if f_move < 0 else "SHORT"
                if not _regime_ok(macro_moves, direction):
                    continue
                sim = _simulate(fdf, i, direction)
                if sim:
                    trades.append(
                        SimTrade(
                            date=date_s,
                            setup_type="divergence",
                            focus=focus,
                            leader=leader,
                            direction=direction,
                            corr=round(corr, 3),
                            lag=lag,
                            leader_move=round(l_move, 2),
                            focus_move=round(f_move, 2),
                            win=sim["return_pct"] > 0,
                            **sim,
                        )
                    )

    return trades


def _summary(trades: List[SimTrade]) -> Dict[str, Any]:
    if not trades:
        return {"n": 0}
    rets = [t.return_pct for t in trades]
    wins = sum(1 for t in trades if t.win)
    return {
        "n": len(trades),
        "wins": wins,
        "win_rate": round(100 * wins / len(trades), 1),
        "avg_return": round(float(np.mean(rets)), 2),
        "median_return": round(float(np.median(rets)), 2),
        "total_return": round(float(np.sum(rets)), 2),
        "stop_rate": round(100 * sum(1 for t in trades if t.hit_stop) / len(trades), 1),
        "target_rate": round(100 * sum(1 for t in trades if t.hit_target) / len(trades), 1),
    }


def write_report(
    all_trades: List[SimTrade],
    path: str,
    meta: Dict[str, Any],
) -> None:
    by_type: Dict[str, List[SimTrade]] = defaultdict(list)
    for t in all_trades:
        by_type[t.setup_type].append(t)

    lines = [
        "# Setup P&L backtest (actionable rules)",
        "",
        f"> Generated: **{meta['generated']}**",
        f"> Period: **{meta['period']}** | Hold: **{HOLD_DAYS}d** max | "
        f"Corr window: **{CORR_LOOKBACK_DAYS}d** | Min |r|: **{MIN_CORR_ABS}** | Min hit: **{MIN_OOS_HIT}%**",
        f"> Focus tickers: {len(meta['focus'])} | Simulated trades: **{len(all_trades)}**",
        "",
        "## Already available (relationship validation only)",
        "",
        "- `BACKTEST_LEAD_LAG.md` + `data/BACKTEST_LEAD_LAG.csv` — correlation & directional hit rates (not P&L)",
        "- This file — **simulated P&L** using catch_up / divergence rules + stops/targets",
        "",
        "## Overall",
        "",
    ]
    overall = _summary(all_trades)
    if overall["n"] == 0:
        lines.append("_No trades generated — loosen filters or extend period._\n")
    else:
        lines.extend([
            "| Metric | Value |",
            "|--------|-------|",
            f"| Trades | {overall['n']} |",
            f"| Win rate | {overall['win_rate']}% |",
            f"| Avg return / trade | {overall['avg_return']:+.2f}% |",
            f"| Median return | {overall['median_return']:+.2f}% |",
            f"| Sum of returns (not compounded) | {overall['total_return']:+.2f}% |",
            f"| Stopped out | {overall['stop_rate']}% |",
            f"| Hit target | {overall['target_rate']}% |",
            "",
        ])

    lines.append("## By setup type\n")
    for st in ("catch_up", "divergence"):
        s = _summary(by_type.get(st, []))
        lines.append(f"### {st}")
        if s["n"] == 0:
            lines.append("_No trades._\n")
        else:
            lines.append(
                f"- Trades: **{s['n']}** | Win: **{s['win_rate']}%** | "
                f"Avg: **{s['avg_return']:+.2f}%** | Median: **{s['median_return']:+.2f}%**\n"
            )

    lines.extend(["## By focus ticker\n", "| Focus | Trades | Win% | Avg% |", "|-------|--------|------|------|"])
    by_focus: Dict[str, List[SimTrade]] = defaultdict(list)
    for t in all_trades:
        by_focus[t.focus].append(t)
    for foc in sorted(by_focus.keys()):
        s = _summary(by_focus[foc])
        if s["n"]:
            lines.append(f"| {foc} | {s['n']} | {s['win_rate']}% | {s['avg_return']:+.2f}% |")

    lines.extend([
        "",
        "## Last 40 trades (most recent)",
        "",
        "| Date | Type | Dir | Focus | Leader | Corr | Ret% | Stop | Tgt |",
        "|------|------|-----|-------|--------|------|------|------|-----|",
    ])
    for t in sorted(all_trades, key=lambda x: x.date)[-40:]:
        lines.append(
            f"| {t.date} | {t.setup_type} | {t.direction} | {t.focus} | {t.leader} | "
            f"{t.corr:+.2f} | {t.return_pct:+.2f}% | {t.hit_stop} | {t.hit_target} |"
        )

    lines.extend([
        "",
        f"## CSV",
        "",
        f"`{meta['csv_path']}`",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"python backtest_setups.py --years {meta['years']}",
        "```",
        "",
    ])
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=1)
    p.add_argument("--focus", default=",".join(DEFAULT_FOCUS))
    p.add_argument("--out", default="BACKTEST_SETUPS.md")
    p.add_argument("--csv", default="data/BACKTEST_SETUPS.csv")
    p.add_argument(
        "--adaptive",
        action="store_true",
        help="Apply learning filters: lag>=1, no divergence, no BUY catch-up, blocked pairs",
    )
    args = p.parse_args()
    if args.adaptive:
        os.environ["REQUIRE_LEADER_PRIOR_DAY"] = "1"
        os.environ["DISABLE_DIVERGENCE"] = "1"
        os.environ["DISABLE_BUY_CATCHUP"] = "1"
    period = f"{args.years}y"
    focus_list = [x.strip().upper() for x in args.focus.split(",") if x.strip()]

    all_syms = set(focus_list) | set(MACRO_NODES.keys())
    for f in focus_list:
        all_syms.update(_nodes_for(f))

    print(f"Downloading {len(all_syms)} symbols ({period})...")
    data = _download(sorted(all_syms), period)
    print(f"Loaded {len(data)} symbols")

    all_trades: List[SimTrade] = []
    for focus in focus_list:
        if focus not in data:
            continue
        nodes = [n for n in _nodes_for(focus) if n in data]
        print(f"  {focus}: {len(nodes)} peers...")
        for leader in nodes:
            all_trades.extend(backtest_pair(focus, leader, data))

    # dedupe same day+focus+type+direction (keep first)
    seen = set()
    deduped: List[SimTrade] = []
    for t in sorted(all_trades, key=lambda x: x.date):
        key = (t.date, t.focus, t.setup_type, t.direction)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    all_trades = deduped

    os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
    if all_trades:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(asdict(all_trades[0]).keys()))
            w.writeheader()
            for t in all_trades:
                w.writerow(asdict(t))

    meta = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period": period,
        "years": args.years,
        "focus": focus_list,
        "csv_path": args.csv,
    }
    write_report(all_trades, args.out, meta)
    s = _summary(all_trades)
    print(f"Done: {s.get('n', 0)} trades → {args.out} + {args.csv}")
    if s.get("n"):
        print(f"  Win {s['win_rate']}% | Avg {s['avg_return']:+.2f}% | Median {s['median_return']:+.2f}%")


if __name__ == "__main__":
    main()
