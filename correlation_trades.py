#!/usr/bin/env python3
"""
Correlation trades: every |r| >= 0.60 movement pair → logged trade with stop/target.
Central store + 7-day outcome updates after each pipeline run.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from pipeline_config import HOLD_DAYS
from pipeline_core import MovementCorrelation
from returns_align import last_price
from trade_levels import calculate_levels

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
CORR_TRADES_JSONL = os.path.join(DATA_DIR, "correlation_trades.jsonl")
CORR_TRADES_CSV = os.path.join(DATA_DIR, "correlation_trades.csv")
CORR_TRADES_REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CORRELATION_TRADES.md")

CORR_TRADE_MIN_R = float(os.getenv("CORR_TRADE_MIN_R", "0.60"))
CORR_TRACK_DAYS = int(os.getenv("CORR_TRACK_DAYS", "7"))
CORR_MAX_TRADES_PER_SCAN = int(os.getenv("CORR_MAX_TRADES_PER_SCAN", "80"))


@dataclass
class CorrelationTrade:
    date: str
    time: str
    stock_leader: str
    stock_follower: str
    r: float
    hit: Optional[float]
    trade: str
    entry_price: float
    stop_loss: float
    take_win: float
    leader_move_1d: float = 0.0
    follower_move_1d: float = 0.0
    lag_days: int = 0
    status: str = "open"
    trade_id: str = ""
    scan_id: str = ""
    logged_at: str = ""

    def row_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "time": self.time,
            "stock_leader": self.stock_leader,
            "stock_follower": self.stock_follower,
            "r": round(self.r, 3),
            "hit": self.hit,
            "trade": self.trade,
            "stop_loss": self.stop_loss,
            "take_win": self.take_win,
            "entry_price": self.entry_price,
            "leader_move_1d": self.leader_move_1d,
            "follower_move_1d": self.follower_move_1d,
            "lag_days": self.lag_days,
            "status": self.status,
            "trade_id": self.trade_id,
            "scan_id": self.scan_id,
            "logged_at": self.logged_at,
        }


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _get_df(data: Dict[str, pd.DataFrame], sym: str) -> Optional[pd.DataFrame]:
    if sym in data:
        return data[sym]
    su = sym.upper()
    for k, v in data.items():
        if k.upper() == su:
            return v
    return None


def _leader_follower(c: MovementCorrelation) -> Tuple[str, str, float, float]:
    """Return leader, follower, leader 1d%, follower 1d%."""
    if c.lag_days > 0:
        return c.leader, c.focus, c.leader_move_1d, c.focus_move_1d
    if c.lag_days < 0:
        return c.focus, c.leader, c.focus_move_1d, c.leader_move_1d
    if abs(c.leader_move_1d) >= abs(c.focus_move_1d):
        return c.leader, c.focus, c.leader_move_1d, c.focus_move_1d
    return c.focus, c.leader, c.focus_move_1d, c.leader_move_1d


def _trade_direction_simple(corr: float, leader_move: float) -> str:
    """Momentum follow on positive corr; inverse on negative corr."""
    if corr >= 0:
        return "BUY" if leader_move > 0 else "SHORT"
    return "SHORT" if leader_move > 0 else "BUY"


def build_correlation_trades(
    correlations: List[MovementCorrelation],
    data: Dict[str, pd.DataFrame],
    scan_time: Optional[str] = None,
) -> List[CorrelationTrade]:
    now = datetime.now()
    scan_time = scan_time or now.strftime("%Y-%m-%d %H:%M:%S")
    date_s = scan_time[:10]
    time_s = scan_time[11:19] if len(scan_time) > 11 else now.strftime("%H:%M:%S")
    scan_id = now.strftime("%Y%m%d%H%M%S")

    trades: List[CorrelationTrade] = []
    seen: set = set()

    ranked = sorted(
        [c for c in correlations if abs(c.corr) >= CORR_TRADE_MIN_R],
        key=lambda x: abs(x.corr),
        reverse=True,
    )[:CORR_MAX_TRADES_PER_SCAN]

    for c in ranked:
        leader, follower, l_move, f_move = _leader_follower(c)
        key = (date_s, leader.upper(), follower.upper())
        if key in seen:
            continue
        seen.add(key)

        direction = _trade_direction_simple(c.corr, l_move)
        df = _get_df(data, follower)
        entry = last_price(data, follower)
        if entry <= 0:
            continue

        if df is not None and len(df) >= 20:
            lv = calculate_levels(follower, direction, df, conviction=4, hold_days=HOLD_DAYS)
            if lv and lv.entry_price > 0:
                entry, stop, target = lv.entry_price, lv.stop_loss, lv.target_price
            else:
                stop = round(entry * (0.95 if direction == "BUY" else 1.05), 2)
                target = round(entry * (1.10 if direction == "BUY" else 0.90), 2)
        else:
            stop = round(entry * (0.95 if direction == "BUY" else 1.05), 2)
            target = round(entry * (1.10 if direction == "BUY" else 0.90), 2)

        tid = f"{scan_id}-{leader}-{follower}"[:64]
        trades.append(
            CorrelationTrade(
                date=date_s,
                time=time_s,
                stock_leader=leader,
                stock_follower=follower,
                r=c.corr,
                hit=c.hit_rate,
                trade=direction,
                entry_price=entry,
                stop_loss=stop,
                take_win=target,
                leader_move_1d=l_move,
                follower_move_1d=f_move,
                lag_days=c.lag_days,
                status="open",
                trade_id=tid,
                scan_id=scan_id,
                logged_at=now.isoformat(),
            )
        )
    return trades


def load_all() -> List[Dict[str, Any]]:
    if not os.path.exists(CORR_TRADES_JSONL):
        return []
    out = []
    with open(CORR_TRADES_JSONL) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def save_all(records: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    with open(CORR_TRADES_JSONL, "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _dedupe(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Latest row per (date, leader, follower)."""
    seen: Dict[tuple, Dict[str, Any]] = {}
    for r in sorted(records, key=lambda x: x.get("logged_at", "")):
        key = (
            (r.get("date") or "")[:10],
            (r.get("stock_leader") or "").upper(),
            (r.get("stock_follower") or "").upper(),
        )
        seen[key] = r
    return list(seen.values())


def log_correlation_trades(
    trades: List[CorrelationTrade],
    *,
    telegram_sent: bool = False,
) -> int:
    _ensure_dir()
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for r in _dedupe(load_all()):
        by_key[
            (
                (r.get("date") or "")[:10],
                (r.get("stock_leader") or "").upper(),
                (r.get("stock_follower") or "").upper(),
            )
        ] = r

    n = 0
    for t in trades:
        rec = t.row_dict()
        rec["setup_type"] = "corr_trade"
        rec["ticker"] = t.stock_follower
        rec["leader"] = t.stock_leader
        rec["direction"] = t.trade
        rec["target_price"] = t.take_win
        rec["telegram_sent"] = telegram_sent
        if not rec.get("outcomes"):
            prev = by_key.get((t.date, t.stock_leader.upper(), t.stock_follower.upper()))
            rec["outcomes"] = (prev or {}).get("outcomes") or {}
        key = (t.date, t.stock_leader.upper(), t.stock_follower.upper())
        if key not in by_key:
            n += 1
        by_key[key] = rec

    save_all(list(by_key.values()))
    export_csv(list(by_key.values()))
    return n


def update_correlation_outcomes(track_days: int = CORR_TRACK_DAYS) -> int:
    """Refresh open correlation trades for up to track_days."""
    from trade_tracker import _fwd_return, _signed, _stop_target_hit

    records = load_all()
    if not records:
        return 0
    today = datetime.now().date()
    updated = 0

    for rec in records:
        if not rec.get("stock_follower"):
            continue
        d_str = (rec.get("date") or rec.get("scan_time") or "")[:10]
        if not d_str:
            continue
        try:
            signal_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        age = (today - signal_date).days
        if age < 0 or age > track_days:
            if age > track_days and rec.get("status") == "open":
                rec["status"] = "expired"
                updated += 1
            continue

        follower = rec.get("stock_follower") or rec.get("ticker")
        direction = rec.get("trade") or rec.get("direction", "BUY")
        oc = rec.get("outcomes") or {}
        entry = float(rec.get("entry_price") or 0)
        stop = float(rec.get("stop_loss") or 0)
        target = float(rec.get("take_win") or rec.get("target_price") or 0)

        for d in range(1, track_days + 1):
            if age >= d:
                oc[f"ret_{d}d"] = _signed(direction, _fwd_return(follower, d_str, d))

        if age >= 1 and entry > 0:
            hits = _stop_target_hit(
                follower, d_str, direction, entry, stop, target, max_days=track_days
            )
            oc.update(hits)

        last_px = _fwd_return(follower, d_str, min(age, track_days))
        if last_px is not None:
            oc["last_price_ret"] = _signed(direction, last_px)

        if oc.get("stop_hit"):
            rec["status"] = "stopped"
        elif oc.get("target_hit"):
            rec["status"] = "won"
        elif age >= track_days:
            r7 = oc.get(f"ret_{track_days}d")
            if r7 is not None:
                rec["status"] = "won" if r7 > 0 else "lost"
            else:
                rec["status"] = "closed"
        else:
            rec["status"] = "open"

        rec["outcomes"] = oc
        rec["outcomes_updated"] = datetime.now().isoformat()
        updated += 1

    if updated:
        save_all(records)
    export_csv(records)
    write_report(records)
    return updated


def export_csv(records: Optional[List[Dict[str, Any]]] = None) -> str:
    records = _dedupe(records if records is not None else load_all())
    _ensure_dir()
    fields = [
        "date",
        "time",
        "stock_leader",
        "stock_follower",
        "r",
        "hit",
        "trade",
        "entry_price",
        "stop_loss",
        "take_win",
        "status",
        "leader_move_1d",
        "follower_move_1d",
        "lag_days",
        "ret_1d",
        "ret_2d",
        "ret_3d",
        "ret_4d",
        "ret_5d",
        "ret_6d",
        "ret_7d",
        "stop_hit",
        "target_hit",
        "trade_id",
        "logged_at",
    ]
    with open(CORR_TRADES_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(records, key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True):
            row = {**r, **(r.get("outcomes") or {})}
            if row.get("hit") is None:
                row["hit"] = ""
            w.writerow(row)
    return CORR_TRADES_CSV


def write_report(records: Optional[List[Dict[str, Any]]] = None) -> str:
    records = _dedupe(records if records is not None else load_all())
    open_t = [r for r in records if r.get("status") == "open"]
    closed = [r for r in records if r.get("status") not in ("open", None)]

    lines = [
        "# Correlation trades",
        "",
        f"> Updated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**",
        f"> Store: `{CORR_TRADES_JSONL}` · CSV: `{CORR_TRADES_CSV}`",
        f"> Rule: |r| ≥ **{CORR_TRADE_MIN_R}** → trade on **follower** · track **{CORR_TRACK_DAYS}d**",
        "",
        f"| Open | {len(open_t)} |",
        f"| Closed / stopped / won | {len(closed)} |",
        "",
        "## Open (latest)",
        "",
        "| date | time | leader | follower | r | hit | trade | stop | target |",
        "|------|------|--------|----------|---|-----|-------|------|--------|",
    ]
    for r in sorted(open_t, key=lambda x: x.get("logged_at", ""), reverse=True)[:30]:
        hit = r.get("hit")
        hit_s = f"{hit:.0f}%" if hit is not None else "—"
        lines.append(
            f"| {r.get('date','')} | {r.get('time','')} | {r.get('stock_leader','')} | "
            f"{r.get('stock_follower','')} | {r.get('r',0):+.2f} | {hit_s} | {r.get('trade','')} | "
            f"${r.get('stop_loss',0):.2f} | ${r.get('take_win',0):.2f} |"
        )
    if not open_t:
        lines.append("| — | — | — | — | — | — | — | — | — |")

    with open(CORR_TRADES_REPORT, "w") as fh:
        fh.write("\n".join(lines))
    return CORR_TRADES_REPORT


def format_trades_plain(trades: List[CorrelationTrade]) -> List[str]:
    lines = ["", "Correlation trades (|r| >= {:.2f})".format(CORR_TRADE_MIN_R)]
    lines.append(
        "date,time,leader,follower,r,hit,trade,entry,stop_loss,take_win"
    )
    for t in trades[:40]:
        hit_s = f"{t.hit:.0f}%" if t.hit is not None else "—"
        lines.append(
            f"{t.date},{t.time},{t.stock_leader},{t.stock_follower},"
            f"{t.r:+.2f},{hit_s},{t.trade},{t.entry_price:.2f},"
            f"{t.stop_loss:.2f},{t.take_win:.2f}"
        )
    return lines


def format_trades_html(trades: List[CorrelationTrade]) -> List[str]:
    lines = ["", f"<b>Correlation trades</b> (|r| ≥ {CORR_TRADE_MIN_R})"]
    for t in trades[:25]:
        hit_s = f"{t.hit:.0f}%" if t.hit is not None else "—"
        ep, sl, tw = t.entry_price, t.stop_loss, t.take_win
        lines.append(
            f"  • <b>{t.date} {t.time}</b>  {t.stock_leader} → {t.stock_follower}  "
            f"r={t.r:+.2f} hit {hit_s}  <b>{t.trade}</b> @ ${ep:.2f}  "
            f"stop ${sl:.2f} · win ${tw:.2f}"
        )
    if len(trades) > 25:
        lines.append(f"  <i>…and {len(trades) - 25} more in correlation_trades.csv</i>")
    return lines
