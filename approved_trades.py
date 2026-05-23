#!/usr/bin/env python3
"""
Select 0–N high-conviction trades: v2 filters + playbook + unconventional alt score.
Only these go to Telegram as "trades to carry out".
"""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from alt_signals import score_alt_signals
from pair_playbook import PairPlaybook
from pipeline_config import (
    FALLBACK_ALT_SCORE,
    MAX_TRADES_PER_SCAN,
    MIN_ALT_SCORE,
    MIN_CORR_ACTIONABLE,
    MIN_CORR_FALLBACK,
    PIPELINE_ACTIONABLE_US,
    TARGET_MIN_TRADES_PER_SCAN,
)
from pipeline_core import ChainPrediction
from pipeline_filters import filter_candidate, select_portfolio, theme_of
from returns_align import last_valid_end_idx

logger = logging.getLogger(__name__)

ACTIONABLE_US_ONLY = PIPELINE_ACTIONABLE_US


def _valid_price(x: Any) -> bool:
    try:
        v = float(x)
        return v > 0 and math.isfinite(v)
    except (TypeError, ValueError):
        return False


def _us_liquid_set() -> Set[str]:
    from universe import _load_us_universe

    return set(_load_us_universe())


def is_actionable_ticker(ticker: str) -> bool:
    if not ACTIONABLE_US_ONLY:
        return True
    t = (ticker or "").upper().strip()
    if not t or "^" in t:
        return False
    if "." in t:
        return False
    us = _us_liquid_set()
    return t in us


@dataclass
class ApprovedTrade:
    ticker: str
    direction: str
    leader: str
    source: str
    entry_price: float
    stop_loss: float
    target_price: float
    position_pct: float
    corr: float
    spread_z: float
    hit_rate: Optional[float]
    chain_path: str
    alt_score: float
    alt_reasons: List[str] = field(default_factory=list)
    expected_by_date: str = ""
    risk_pct: float = 0.0
    leader_move_pct: float = 0.0

    def telegram_lines(self) -> List[str]:
        emoji = "📈" if self.direction == "BUY" else "📉"
        hit_s = f"{self.hit_rate:.0f}%" if self.hit_rate is not None else "—"
        lines = [
            f"{emoji} <b>{self.direction} {self.ticker}</b> @ <b>${self.entry_price:.2f}</b>",
            f"  Leader <b>{self.leader}</b> {self.leader_move_pct:+.1f}% · r={self.corr:+.2f} · z={self.spread_z:+.1f} · hit {hit_s}",
            f"  Stop ${self.stop_loss:.2f} · Target ${self.target_price:.2f} · ~{self.position_pct:.0f}% size",
            f"  <i>{self.chain_path}</i>",
            f"  Edge score <b>{self.alt_score:.0f}</b>: " + "; ".join(self.alt_reasons[:4]),
        ]
        if self.expected_by_date:
            lines.append(f"  Exit by {self.expected_by_date}")
        return lines


def _from_chain_prediction(
    p: ChainPrediction,
    pb: PairPlaybook,
    alt_extra: dict,
    *,
    require_filter: bool = True,
) -> Optional[ApprovedTrade]:
    if not _valid_price(p.entry_price) or not _valid_price(p.stop_loss) or not _valid_price(p.target_price):
        return None
    if not is_actionable_ticker(p.focus):
        return None
    ok_pb, _ = pb.allows(p.focus, p.leader, p.direction, p.prediction_type, use_static=True)
    if require_filter and not ok_pb:
        return None
    alt = score_alt_signals(
        focus=p.focus,
        leader=p.leader,
        direction=p.direction,
        corr=p.corr,
        hit_rate=p.hit_rate,
        playbook_ok=ok_pb,
        **alt_extra,
    )
    return ApprovedTrade(
        ticker=p.focus,
        direction=p.direction,
        leader=p.leader,
        source="v2_chain",
        entry_price=p.entry_price,
        stop_loss=p.stop_loss,
        target_price=p.target_price,
        position_pct=p.position_pct or 5.0,
        corr=p.corr,
        spread_z=p.spread_z,
        hit_rate=p.hit_rate,
        chain_path=p.chain_path,
        alt_score=alt.score,
        alt_reasons=alt.reasons,
        expected_by_date=p.expected_by_date,
        risk_pct=p.risk_pct,
        leader_move_pct=p.leader_move_pct,
    )


def _from_correlation_trade(
    t,
    rets: pd.DataFrame,
    end_idx: int,
    pb: PairPlaybook,
    alt_extra: dict,
    *,
    require_filter: bool = True,
    min_corr: float = MIN_CORR_ACTIONABLE,
) -> Optional[ApprovedTrade]:
    focus = t.stock_follower
    leader = t.stock_leader
    if not is_actionable_ticker(focus):
        return None
    if abs(t.r) < min_corr:
        return None
    if not _valid_price(t.entry_price) or not _valid_price(t.stop_loss) or not _valid_price(t.take_win):
        return None

    if require_filter:
        ok, msg = filter_candidate(
            focus=focus,
            leader=leader,
            direction=t.trade,
            prediction_type="corr_pair",
            lag_days=t.lag_days or 0,
            leader_prior_pct=t.leader_move_1d,
            focus_move_pct=t.follower_move_1d,
            corr=t.r,
            rets=rets,
            end_idx=end_idx,
        )
        if not ok:
            logger.debug("corr filter %s→%s: %s", leader, focus, msg)
            return None

    ok_pb, _ = pb.allows(focus, leader, t.trade, "corr_pair", use_static=True)
    alt = score_alt_signals(
        focus=focus,
        leader=leader,
        direction=t.trade,
        corr=t.r,
        hit_rate=t.hit,
        playbook_ok=ok_pb,
        rets=rets,
        end_idx=end_idx,
        global_chains=alt_extra.get("global_chains"),
    )

    risk = abs(t.entry_price - t.stop_loss) / t.entry_price * 100 if t.entry_price else 5.0
    return ApprovedTrade(
        ticker=focus,
        direction=t.trade,
        leader=leader,
        source="corr_pair",
        entry_price=t.entry_price,
        stop_loss=t.stop_loss,
        target_price=t.take_win,
        position_pct=min(10.0, (2.0 / risk) * 100) if risk > 0 else 5.0,
        corr=t.r,
        spread_z=alt.spread_z or 0.0,
        hit_rate=t.hit,
        chain_path=f"{leader} → {focus}",
        alt_score=alt.score,
        alt_reasons=alt.reasons,
        expected_by_date="",
        risk_pct=risk,
        leader_move_pct=t.leader_move_1d,
    )


def _dedupe_and_rank(candidates: List[ApprovedTrade]) -> List[ApprovedTrade]:
    by_ticker: Dict[str, ApprovedTrade] = {}
    for c in sorted(candidates, key=lambda x: x.alt_score, reverse=True):
        key = c.ticker.upper()
        if key not in by_ticker:
            by_ticker[key] = c
    unique = list(by_ticker.values())
    unique.sort(key=lambda x: (x.alt_score, abs(x.corr)), reverse=True)
    return unique


def _pick_with_caps(
    ranked: List[ApprovedTrade],
    max_trades: int,
    min_score: float,
    notes: List[str],
) -> List[ApprovedTrade]:
    chosen: List[ApprovedTrade] = []
    theme_counts: Dict[str, int] = {}
    for c in ranked:
        if c.alt_score < min_score:
            continue
        if len(chosen) >= max_trades:
            break
        th = theme_of(c.ticker)
        if theme_counts.get(th, 0) >= 1:
            notes.append(f"{c.ticker}: theme {th} cap")
            continue
        chosen.append(c)
        theme_counts[th] = theme_counts.get(th, 0) + 1
    return chosen


def select_approved_trades(
    predictions: List[ChainPrediction],
    correlation_trades: List[Any],
    rets: pd.DataFrame,
    global_chains: Optional[List[Any]] = None,
    max_trades: int = MAX_TRADES_PER_SCAN,
) -> Tuple[List[ApprovedTrade], List[str]]:
    """
    Merge v2 chain + correlation pairs; rank by alt score.
    Uses strict filters first, then fallback so most scans have 1+ trade.
    """
    pb = PairPlaybook()
    pb.load_static()
    end_idx = last_valid_end_idx(rets) if not rets.empty else -1
    alt_extra = {"rets": rets, "end_idx": end_idx, "global_chains": global_chains}

    strict: List[ApprovedTrade] = []
    soft: List[ApprovedTrade] = []
    notes: List[str] = []

    for p in predictions:
        at = _from_chain_prediction(p, pb, alt_extra, require_filter=True)
        if at:
            strict.append(at)

    for t in correlation_trades:
        if rets.empty or end_idx < 0:
            continue
        at = _from_correlation_trade(t, rets, end_idx, pb, alt_extra, require_filter=True)
        if at:
            strict.append(at)
        at_soft = _from_correlation_trade(
            t, rets, end_idx, pb, alt_extra,
            require_filter=False,
            min_corr=MIN_CORR_FALLBACK,
        )
        if at_soft:
            soft.append(at_soft)

    ranked = _dedupe_and_rank(strict)
    chosen = _pick_with_caps(ranked, max_trades, MIN_ALT_SCORE, notes)

    if len(chosen) < TARGET_MIN_TRADES_PER_SCAN:
        pool = _dedupe_and_rank(strict + soft)
        fallback = _pick_with_caps(pool, max_trades, FALLBACK_ALT_SCORE, notes)
        if fallback and not chosen:
            notes.append(f"Fallback: alt score ≥{FALLBACK_ALT_SCORE:.0f}")
            chosen = fallback
        elif len(fallback) > len(chosen):
            notes.append(f"Topped up to {len(fallback)} (fallback score)")
            chosen = fallback

    if not chosen and soft:
        pool = _dedupe_and_rank(soft)
        chosen = _pick_with_caps(pool, min(max_trades, 2), 0, notes)
        if chosen:
            notes.append("Last resort: top corr pairs (valid prices, no regime filter)")

    if not chosen:
        notes.append("No actionable candidates today")
        return [], notes

    return chosen, notes


def format_approved_telegram(
    approved: List[ApprovedTrade],
    scan_time: str,
    context_lines: Optional[List[str]] = None,
    performance_lines: Optional[List[str]] = None,
) -> str:
    lines = [
        "<b>Trades to carry out</b>",
        f"<i>{scan_time}</i> · max {MAX_TRADES_PER_SCAN} · US liquid · fade + alt data",
        "",
    ]
    if not approved:
        lines.append("<i>No trades met filters, playbook, and unconventional edge score today.</i>")
    else:
        for at in approved:
            lines.extend(at.telegram_lines())
            lines.append("")

    if context_lines:
        lines.append("<b>Context</b> (paths most screens miss)")
        lines.extend(context_lines[:8])
        lines.append("")

    if performance_lines:
        lines.append("<b>Open P&amp;L</b> (prior signals)")
        lines.extend(performance_lines[:12])

    return "\n".join(lines)


def log_approved_trades(scan_time: str, approved: List[ApprovedTrade], telegram_sent: bool) -> None:
    from trade_tracker import SETUP_FILE
    import json
    from datetime import datetime

    os.makedirs(os.path.dirname(SETUP_FILE) or ".", exist_ok=True)
    scan_id = datetime.now().strftime("%Y%m%d%H%M%S")
    for at in approved:
        rec = {
            "trade_id": f"{scan_id}-{at.ticker}-approved",
            "logged_at": datetime.now().isoformat(),
            "scan_time": scan_time,
            "scan_id": scan_id,
            "telegram_sent": telegram_sent,
            "status": "open",
            "pipeline": "approved_v2",
            "setup_type": at.source,
            "ticker": at.ticker,
            "direction": at.direction,
            "leader": at.leader,
            "entry_price": at.entry_price,
            "stop_loss": at.stop_loss,
            "target_price": at.target_price,
            "position_pct": at.position_pct,
            "corr": at.corr,
            "spread_z": at.spread_z,
            "hit_rate": at.hit_rate,
            "alt_score": at.alt_score,
            "thesis": "; ".join(at.alt_reasons),
            "outcomes": {},
        }
        with open(SETUP_FILE, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
