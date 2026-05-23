#!/usr/bin/env python3
"""
Paper portfolio: track equity if you took every approved trade at suggested size.
Tier 3 validation — compound returns with 2% risk per trade sizing.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
PAPER_FILE = os.path.join(DATA_DIR, "paper_portfolio.json")
STARTING_EQUITY = float(os.getenv("PAPER_START_EQUITY", "100000"))
RISK_PER_TRADE_PCT = float(os.getenv("PAPER_RISK_PCT", "2.0"))


def _load() -> Dict[str, Any]:
    if not os.path.exists(PAPER_FILE):
        return {
            "starting_equity": STARTING_EQUITY,
            "equity": STARTING_EQUITY,
            "positions": [],
            "closed": [],
            "updated": None,
        }
    with open(PAPER_FILE) as fh:
        return json.load(fh)


def _save(state: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    state["updated"] = datetime.now().isoformat()
    with open(PAPER_FILE, "w") as fh:
        json.dump(state, fh, indent=2)


def _position_value(equity: float, position_pct: float) -> float:
    return equity * (position_pct / 100.0)


def add_approved_trades(trades: List[Any]) -> int:
    """Register new approved trades (skip if same ticker+direction already open)."""
    if not trades:
        return 0
    state = _load()
    open_keys = {
        (p["ticker"].upper(), p["direction"])
        for p in state.get("positions", [])
    }
    added = 0
    for at in trades:
        key = (at.ticker.upper(), at.direction)
        if key in open_keys:
            continue
        risk_pct = getattr(at, "risk_pct", 5) or 5
        pos_pct = getattr(at, "position_pct", 5) or min(10, (RISK_PER_TRADE_PCT / risk_pct) * 100)
        notional = _position_value(state["equity"], pos_pct)
        state["positions"].append({
            "ticker": at.ticker.upper(),
            "direction": at.direction,
            "entry_price": at.entry_price,
            "stop_loss": at.stop_loss,
            "target_price": at.target_price,
            "position_pct": pos_pct,
            "notional": round(notional, 2),
            "opened_at": datetime.now().isoformat(),
            "leader": getattr(at, "leader", ""),
            "alt_score": getattr(at, "alt_score", 0),
        })
        open_keys.add(key)
        added += 1
    if added:
        _save(state)
    return added


def mark_to_market() -> Dict[str, Any]:
    """Update open positions; close on stop/target; adjust equity."""
    state = _load()
    if not state.get("positions"):
        _save(state)
        return state

    from correlation_trades import _fetch_latest_prices

    tickers = [p["ticker"] for p in state["positions"]]
    prices = _fetch_latest_prices(tickers)
    still_open: List[Dict[str, Any]] = []

    for p in state["positions"]:
        ticker = p["ticker"]
        direction = p["direction"]
        entry = float(p["entry_price"])
        stop = float(p["stop_loss"])
        target = float(p["target_price"])
        notional = float(p["notional"])
        now = prices.get(ticker.upper())
        if not now or now <= 0 or entry <= 0:
            still_open.append(p)
            continue

        raw_ret = (now / entry - 1)
        if direction == "SHORT":
            raw_ret = -raw_ret
        pnl_dollars = notional * raw_ret

        closed = False
        reason = ""
        if direction == "BUY":
            if now <= stop:
                pnl_dollars = notional * ((stop / entry) - 1)
                closed, reason = True, "stop"
            elif now >= target:
                pnl_dollars = notional * ((target / entry) - 1)
                closed, reason = True, "target"
        else:
            if now >= stop:
                pnl_dollars = notional * (-((stop / entry) - 1))
                closed, reason = True, "stop"
            elif now <= target:
                pnl_dollars = notional * (-((target / entry) - 1))
                closed, reason = True, "target"

        if closed:
            state["equity"] = round(state["equity"] + pnl_dollars, 2)
            state.setdefault("closed", []).append({
                **p,
                "exit_price": now,
                "pnl_dollars": round(pnl_dollars, 2),
                "pnl_pct": round(raw_ret * 100, 2),
                "close_reason": reason,
                "closed_at": datetime.now().isoformat(),
            })
        else:
            p["current_price"] = now
            p["unrealized_pnl"] = round(pnl_dollars, 2)
            p["unrealized_pct"] = round(raw_ret * 100, 2)
            still_open.append(p)

    state["positions"] = still_open
    _save(state)
    return state


def get_portfolio_summary() -> Dict[str, Any]:
    state = mark_to_market()
    start = float(state.get("starting_equity", STARTING_EQUITY))
    equity = float(state.get("equity", start))
    closed = state.get("closed", [])
    wins = sum(1 for c in closed if c.get("pnl_dollars", 0) > 0)
    n_closed = len(closed)
    return {
        "equity": equity,
        "starting_equity": start,
        "total_return_pct": round((equity / start - 1) * 100, 2) if start else 0,
        "trade_count": n_closed,
        "win_rate": round(100 * wins / n_closed, 1) if n_closed else 0,
        "open_positions": len(state.get("positions", [])),
    }
