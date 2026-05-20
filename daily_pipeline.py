#!/usr/bin/env python3
"""
Automated daily output: movements, chain predictions, amounts, dates.
Stores trades, updates outcomes, writes scoreboard. Used by Railway cron.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import List, Tuple

from correlation_map import _bulk_download, _returns_matrix
from momentum_chain import MomentumChainFinder
from pair_playbook import PairPlaybook
from pipeline_config import MAX_TRADES_PER_SCAN, TARGET_WIN_RATE
from pipeline_core import ChainPrediction, MovementSnapshot, generate_predictions
from pipeline_filters import select_portfolio
from trade_tracker import SETUP_FILE, update_outcomes, write_report as write_tracker_report

logger = logging.getLogger(__name__)
SCOREBOARD = "SCOREBOARD.md"
DAILY_OUTPUT = "data/latest_pipeline_output.txt"


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_daily_message(
    scan_time: str,
    movers: List[MovementSnapshot],
    predictions: List[ChainPrediction],
) -> str:
    lines = [
        "<b>Pipeline alert</b>",
        f"<i>{_esc(scan_time)}</i>",
        "",
        "<b>Stock movements</b>",
    ]
    for m in movers[:10]:
        lines.append(
            f"  • <b>{_esc(m.ticker)}</b> ${m.price:.2f}  "
            f"<b>{m.move_1d_pct:+.1f}%</b> today  ({m.move_5d_pct:+.1f}% / 5d)"
        )

    if not predictions:
        lines.append("")
        lines.append("<i>No chain predictions passed filters this scan.</i>")
        return "\n".join(lines)

    lines.extend(["", "<b>Chain predictions &amp; proposed trades</b>"])
    for p in predictions[:6]:
        emoji = "📈" if p.direction == "BUY" else "📉"
        hit_s = f"{p.hit_rate:.0f}%" if p.hit_rate is not None else "—"
        lines.extend([
            "",
            f"{emoji} <b>{p.direction} {p.focus}</b>  <i>{p.prediction_type}</i>",
            f"  Path: {_esc(p.chain_path)}",
            f"  Leader <b>{_esc(p.leader)}</b> {p.leader_move_pct:+.1f}% → "
            f"predict <b>{p.predicted_move_pct:+.1f}%</b> by <b>{_esc(p.expected_by_date)}</b> "
            f"({p.expected_days}d, r={p.corr:+.2f}, z={p.spread_z:+.1f}, hit {hit_s})",
            f"  Entry ${p.entry_price:.2f} · Stop ${p.stop_loss:.2f} · "
            f"Target ${p.target_price:.2f} · Size ~{p.position_pct:.0f}%",
        ])
    return "\n".join(lines)


def format_plain(msg: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", msg).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _log_scan_heartbeat(scan_time: str, proposed_count: int, telegram_sent: bool) -> None:
    os.makedirs(os.path.dirname(SETUP_FILE) or ".", exist_ok=True)
    scan_id = datetime.now().strftime("%Y%m%d%H%M%S")
    rec = {
        "trade_id": f"{scan_id}-scan",
        "logged_at": datetime.now().isoformat(),
        "scan_time": scan_time,
        "scan_id": scan_id,
        "setup_type": "scan_heartbeat",
        "proposed_count": proposed_count,
        "telegram_sent": telegram_sent,
        "pipeline": "map_v1",
    }
    with open(SETUP_FILE, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def log_predictions(
    scan_time: str,
    predictions: List[ChainPrediction],
    telegram_sent: bool,
) -> None:
    os.makedirs(os.path.dirname(SETUP_FILE) or ".", exist_ok=True)
    scan_id = datetime.now().strftime("%Y%m%d%H%M%S")
    for p in predictions:
        rec = {
            "trade_id": f"{scan_id}-{p.focus}-{p.prediction_type[:4]}",
            "logged_at": datetime.now().isoformat(),
            "scan_time": scan_time,
            "scan_id": scan_id,
            "telegram_sent": telegram_sent,
            "status": "open",
            "pipeline": "map_v1",
            **p.to_trade_dict(),
            "outcomes": {},
        }
        with open(SETUP_FILE, "a") as fh:
            f.write(json.dumps(rec) + "\n")


def write_scoreboard() -> str:
    from trade_tracker import load_all, _dedupe_trades

    records = load_all()
    trades = _dedupe_trades([
        r for r in records
        if r.get("ticker") and r.get("setup_type") not in ("scan_heartbeat", "none")
    ])
    closed = [t for t in trades if t.get("outcomes", {}).get("ret_5d") is not None]
    open_t = [t for t in trades if t not in closed]

    lines = [
        "# Scoreboard",
        "",
        f"> Updated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**",
        "",
        f"| Open trades | {len(open_t)} |",
        f"| Scored (5d outcome) | {len(closed)} |",
        "",
    ]
    if closed:
        wins = sum(1 for t in closed if (t.get("outcomes") or {}).get("ret_5d", 0) > 0)
        avg = sum((t.get("outcomes") or {}).get("ret_5d", 0) for t in closed) / len(closed)
        lines.append(f"| Live win rate (5d) | {wins}/{len(closed)} ({100*wins/len(closed):.0f}%) |")
        lines.append(f"| Live avg 5d return | {avg:+.2f}% |")

    lines.extend(["", "## Open", ""])
    if open_t:
        for t in sorted(open_t, key=lambda x: x.get("scan_time", ""), reverse=True)[:20]:
            lines.append(
                f"- {t.get('scan_time','')[:10]} **{t.get('direction')} {t.get('ticker')}** "
                f"@ ${t.get('entry_price', 0):.2f} → target ${t.get('target_price', 0):.2f} "
                f"({t.get('prediction_type', t.get('setup_type',''))})"
            )
    else:
        lines.append("_None_")

    with open(SCOREBOARD, "w") as fh:
        fh.write("\n".join(lines))
    return SCOREBOARD


def run_pipeline(send_telegram: bool = True) -> Tuple[bool, str]:
    """Full automated run."""
    logger.info("Pipeline started %s", datetime.now().isoformat())

    finder = MomentumChainFinder(top_n=15)
    scan_result = finder.scan()
    scan_time = scan_result.scan_time

    data = scan_result.price_cache
    if not data:
        from universe import load_scan_universe
        from correlation_map import _bulk_download

        data = _bulk_download(load_scan_universe()[:300], period="2y")

    rets = _returns_matrix(data)
    focus_list = [p.ticker for p in scan_result.top_volatile[:12]]
    if not focus_list:
        focus_list = list(rets.columns[:12])

    movers, raw_preds = generate_predictions(
        data, rets, focus_list, scan_time, apply_playbook=False,
    )
    predictions, portfolio_blocked = select_portfolio(raw_preds)
    if not raw_preds and not predictions:
        pb = PairPlaybook()
        pb.load_static()
        logger.info(
            "No trades: v2 filters or playbook (target %.0f%%, %d pairs loaded)",
            TARGET_WIN_RATE,
            len(pb._static_allowed),
        )
    elif portfolio_blocked:
        logger.info("Portfolio cap blocked: %s", portfolio_blocked[:5])

    message = format_daily_message(scan_time, movers, predictions)
    plain = format_plain(message)

    os.makedirs(os.path.dirname(DAILY_OUTPUT) or ".", exist_ok=True)
    with open(DAILY_OUTPUT, "w") as fh:
        fh.write(plain)

    sent = False
    if send_telegram:
        from telegram_alerts import TelegramBot
        bot = TelegramBot()
        if bot.enabled:
            sent = bot.send_message(message)

    _log_scan_heartbeat(scan_time, len(predictions), sent)
    log_predictions(scan_time, predictions, sent)
    update_outcomes(min_age_days=1)
    write_scoreboard()
    write_tracker_report()

    logger.info(
        "Pipeline done: universe=%s focus=%d predictions=%d telegram=%s",
        getattr(scan_result, "universe_size", "?"),
        len(focus_list),
        len(predictions),
        sent,
    )
    return True, plain


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok, text = run_pipeline(send_telegram=False)
    print(text)
