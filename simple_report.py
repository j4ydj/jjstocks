#!/usr/bin/env python3
"""
Simple scan output: new trades, existing trades, status, summary.
Used for Telegram and data/latest_pipeline_output.txt.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from approved_trades import ApprovedTrade


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _valid_price(x: Any) -> bool:
    try:
        v = float(x)
        return v > 0 and math.isfinite(v)
    except (TypeError, ValueError):
        return False


def _load_open_positions() -> List[Dict[str, Any]]:
    """Open positions you are tracking (approved layer in trade_setups.jsonl only)."""
    open_list: List[Dict[str, Any]] = []
    seen: set = set()

    try:
        from trade_tracker import load_all, _dedupe_trades

        for r in _dedupe_trades(load_all()):
            if r.get("setup_type") in ("scan_heartbeat", "none"):
                continue
            if r.get("pipeline") != "approved_v2":
                continue
            if not r.get("ticker"):
                continue
            if not _valid_price(r.get("entry_price")):
                continue
            st = r.get("status", "open")
            if st not in ("open", None):
                continue
            key = (r.get("ticker", "").upper(), r.get("direction", ""))
            if key in seen:
                continue
            seen.add(key)
            open_list.append(_normalize_record(r, source="approved"))
    except Exception:
        pass

    open_list.sort(key=lambda x: x.get("scan_time", ""), reverse=True)
    return open_list[:20]


def _normalize_record(r: Dict[str, Any], source: str) -> Dict[str, Any]:
    ticker = r.get("ticker") or r.get("stock_follower") or ""
    direction = r.get("direction") or r.get("trade") or "BUY"
    return {
        "ticker": ticker.upper(),
        "direction": direction,
        "leader": r.get("leader") or r.get("stock_leader") or "",
        "entry_price": float(r.get("entry_price") or 0),
        "stop_loss": float(r.get("stop_loss") or 0),
        "target_price": float(r.get("target_price") or r.get("take_win") or 0),
        "status": r.get("status") or "open",
        "scan_time": (r.get("scan_time") or r.get("date") or "")[:10],
        "position_pct": float(r.get("position_pct") or 5),
        "outcomes": r.get("outcomes") or {},
        "source": source,
        "pnl_pct": r.get("pnl_pct"),
        "current_price": r.get("current_price"),
    }


def _enrich_positions(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not positions:
        return []
    from correlation_trades import enrich_with_latest_prices

    enrich_with_latest_prices(positions)
    for p in positions:
        entry = p.get("entry_price") or 0
        now = p.get("current_price")
        direction = p.get("direction", "BUY")
        if _valid_price(entry) and _valid_price(now):
            raw = (now / entry - 1) * 100
            p["pnl_pct"] = round(raw if direction == "BUY" else -raw, 2)
        oc = p.get("outcomes") or {}
        if oc.get("stop_hit"):
            p["status"] = "stopped"
        elif oc.get("target_hit"):
            p["status"] = "won"
    return positions


def _split_new_vs_existing(
    new_candidates: List[ApprovedTrade],
    open_positions: List[Dict[str, Any]],
) -> Tuple[List[ApprovedTrade], List[ApprovedTrade]]:
    open_keys = {(p["ticker"], p["direction"]) for p in open_positions}
    new_trades: List[ApprovedTrade] = []
    for at in new_candidates:
        if (at.ticker.upper(), at.direction) in open_keys:
            continue
        new_trades.append(at)
    return new_trades, new_candidates


def _trade_line_plain(at: ApprovedTrade) -> str:
    return (
        f"  {at.direction} {at.ticker} @ ${at.entry_price:.2f}  "
        f"stop ${at.stop_loss:.2f}  target ${at.target_price:.2f}  "
        f"({at.leader} → score {at.alt_score:.0f})"
    )


def _position_line_plain(p: Dict[str, Any], *, status_detail: bool = False) -> str:
    ticker = p.get("ticker", "")
    direction = p.get("direction", "")
    entry = p.get("entry_price") or 0
    now = p.get("current_price")
    pnl = p.get("pnl_pct")
    st = p.get("status", "open")
    now_s = f"${now:.2f}" if _valid_price(now) else "—"
    pnl_s = f"{pnl:+.2f}%" if pnl is not None else "—"
    line = f"  {direction} {ticker}  entry ${entry:.2f}  now {now_s}  P&L {pnl_s}  [{st}]"
    if status_detail:
        oc = p.get("outcomes") or {}
        if oc.get("stop_hit"):
            line += "  stop hit"
        elif oc.get("target_hit"):
            line += "  target hit"
        r5 = oc.get("ret_5d") or oc.get("ret_7d")
        if r5 is not None:
            line += f"  ret {r5:+.1f}%"
    return line


def build_summary(
    new_trades: List[ApprovedTrade],
    open_positions: List[Dict[str, Any]],
    paper: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    closed_status = {"won", "lost", "stopped", "closed", "expired"}
    open_ct = len([p for p in open_positions if p.get("status") == "open"])
    closed = [p for p in open_positions if p.get("status") in closed_status]
    pnls = [p["pnl_pct"] for p in open_positions if p.get("pnl_pct") is not None]
    open_pnl = sum(pnls) / len(pnls) if pnls else None

    return {
        "new_count": len(new_trades),
        "open_count": open_ct,
        "closed_count": len(closed),
        "avg_open_pnl": open_pnl,
        "paper_equity": (paper or {}).get("equity"),
        "paper_return_pct": (paper or {}).get("total_return_pct"),
        "paper_trades": (paper or {}).get("trade_count"),
        "paper_win_rate": (paper or {}).get("win_rate"),
    }


def format_simple_report(
    new_trades: List[ApprovedTrade],
    scan_time: str,
    *,
    html: bool = True,
) -> str:
    open_positions = _enrich_positions(_load_open_positions())
    new_only, _ = _split_new_vs_existing(new_trades, open_positions)

    paper = None
    try:
        from paper_portfolio import get_portfolio_summary

        paper = get_portfolio_summary()
    except Exception:
        pass

    summary = build_summary(new_only, open_positions, paper)

    if html:
        return _format_html(new_only, open_positions, summary, scan_time)
    return _format_plain(new_only, open_positions, summary, scan_time)


def _format_plain(
    new_trades: List[ApprovedTrade],
    open_positions: List[Dict[str, Any]],
    summary: Dict[str, Any],
    scan_time: str,
) -> str:
    lines = [
        f"Scan {scan_time}",
        "",
        "=== 1. NEW TRADES ===",
    ]
    if new_trades:
        for at in new_trades:
            lines.append(_trade_line_plain(at))
    else:
        lines.append("  None today.")

    lines.extend(["", "=== 2. EXISTING TRADES (open) ==="])
    open_only = [p for p in open_positions if p.get("status") == "open"]
    if open_only:
        for p in open_only:
            lines.append(
                f"  {p.get('direction')} {p.get('ticker')} @ ${p.get('entry_price', 0):.2f}  "
                f"since {p.get('scan_time', '')[:10]}"
            )
    else:
        lines.append("  None.")

    lines.extend(["", "=== 3. STATUS (existing) ==="])
    if open_only:
        for p in open_only:
            lines.append(_position_line_plain(p, status_detail=True))
    else:
        lines.append("  No open positions.")

    lines.extend(["", "=== 4. SUMMARY ==="])
    lines.append(f"  New today: {summary['new_count']}")
    lines.append(f"  Open: {summary['open_count']}")
    if summary.get("avg_open_pnl") is not None:
        lines.append(f"  Avg open P&L: {summary['avg_open_pnl']:+.2f}%")
    if summary.get("paper_equity"):
        lines.append(
            f"  Paper portfolio: ${summary['paper_equity']:,.0f} "
            f"({summary.get('paper_return_pct', 0):+.1f}% total, "
            f"{summary.get('paper_win_rate', 0):.0f}% win on {summary.get('paper_trades', 0)} closed)"
        )
    return "\n".join(lines)


def _format_html(
    new_trades: List[ApprovedTrade],
    open_positions: List[Dict[str, Any]],
    summary: Dict[str, Any],
    scan_time: str,
) -> str:
    lines = [
        f"<b>Scan</b> <i>{_esc(scan_time)}</i>",
        "",
        "<b>1. New trades</b>",
    ]
    if new_trades:
        for at in new_trades:
            em = "📈" if at.direction == "BUY" else "📉"
            lines.append(
                f"  {em} <b>{at.direction} {at.ticker}</b> @ ${at.entry_price:.2f} · "
                f"stop ${at.stop_loss:.2f} · target ${at.target_price:.2f}"
            )
    else:
        lines.append("  None today.")

    lines.extend(["", "<b>2. Existing trades</b>"])
    open_only = [p for p in open_positions if p.get("status") == "open"]
    if open_only:
        for p in open_only:
            lines.append(
                f"  {p.get('direction')} <b>{p.get('ticker')}</b> @ ${p.get('entry_price', 0):.2f} "
                f"<i>since {p.get('scan_time', '')[:10]}</i>"
            )
    else:
        lines.append("  None.")

    lines.extend(["", "<b>3. Status (existing)</b>"])
    if open_only:
        for p in open_only:
            now = p.get("current_price")
            pnl = p.get("pnl_pct")
            now_s = f"${now:.2f}" if _valid_price(now) else "—"
            pnl_s = f"{pnl:+.2f}%" if pnl is not None else "—"
            lines.append(
                f"  {p.get('direction')} <b>{p.get('ticker')}</b>  now {now_s}  P&amp;L <b>{pnl_s}</b>  "
                f"[{p.get('status')}]"
            )
    else:
        lines.append("  No open positions.")

    lines.extend(["", "<b>4. Summary</b>"])
    lines.append(f"  New: <b>{summary['new_count']}</b> · Open: <b>{summary['open_count']}</b>")
    if summary.get("avg_open_pnl") is not None:
        lines.append(f"  Avg open P&amp;L: <b>{summary['avg_open_pnl']:+.2f}%</b>")
    if summary.get("paper_equity"):
        lines.append(
            f"  Paper: <b>${summary['paper_equity']:,.0f}</b> "
            f"({summary.get('paper_return_pct', 0):+.1f}% all-time)"
        )
    return "\n".join(lines)
