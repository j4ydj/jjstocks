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
from typing import List, Optional, Tuple

from correlation_map import _bulk_download, _returns_matrix
from momentum_chain import MomentumChainFinder
from pair_playbook import PairPlaybook
from pipeline_config import MAX_TRADES_PER_SCAN, TARGET_WIN_RATE
from pipeline_core import (
    ChainPrediction,
    MovementCorrelation,
    MovementSnapshot,
    discover_movement_correlations,
    generate_predictions,
)
from returns_align import build_returns_matrix
from correlation_trades import (
    build_correlation_trades,
    format_trades_html,
    format_trades_plain,
    log_correlation_trades,
    update_correlation_outcomes,
    write_report as write_corr_report,
)
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
    global_index_chains: Optional[List] = None,
    movement_correlations: Optional[List[MovementCorrelation]] = None,
    correlation_trades: Optional[list] = None,
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

    if global_index_chains:
        from global_index_chains import format_global_chains_html

        block = format_global_chains_html(global_index_chains, scan_time)
        if block:
            lines.append(block)

    if movement_correlations:
        lines.extend(["", "<b>Correlated movements</b> (aligned global returns)"])
        for c in movement_correlations[:20]:
            hit_s = f", hit {c.hit_rate:.0f}%" if c.hit_rate is not None else ""
            lag_s = f", lag {c.lag_days}d" if c.lag_days else ""
            lines.append(
                f"  • <b>{_esc(c.leader)}</b> {c.leader_move_1d:+.1f}% ↔ "
                f"<b>{_esc(c.focus)}</b> {c.focus_move_1d:+.1f}%  "
                f"(r={c.corr:+.2f}{lag_s}{hit_s}, {c.layer})"
            )

    if correlation_trades:
        lines.extend(format_trades_html(correlation_trades))

    if not predictions and not correlation_trades:
        lines.append("")
        if movement_correlations:
            lines.append("<i>No |r|≥0.60 trades this scan (see correlations above).</i>")
        else:
            lines.append("<i>No correlated movements or trades found this scan.</i>")
        return "\n".join(lines)

    if not predictions:
        return "\n".join(lines)

    lines.extend(["", "<b>Strict v2 trades</b> (optional layer)"])
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

    import os
    from global_indexes import is_global_mode

    top_n = int(os.getenv("MOMENTUM_TOP_N", "30" if is_global_mode() else "30"))
    focus_n = int(os.getenv("PIPELINE_FOCUS_N", "24" if is_global_mode() else "24"))
    finder = MomentumChainFinder(top_n=top_n)
    scan_result = finder.scan()
    scan_time = scan_result.scan_time

    data = scan_result.price_cache
    if not data:
        from universe import load_scan_universe
        from correlation_map import _bulk_download

        data = _bulk_download(load_scan_universe()[:300], period="2y")

    rets = build_returns_matrix(data)
    if rets.empty:
        logger.error("Returns matrix empty — check PIPELINE_MIN_BARS and download period")
    else:
        logger.info("Returns matrix: %d days × %d symbols", len(rets), len(rets.columns))

    focus_list = [p.ticker for p in scan_result.top_volatile[:focus_n]]
    movement_correlations = discover_movement_correlations(data, rets, focus_list)
    logger.info("Movement correlations discovered: %d", len(movement_correlations))

    corr_trades = build_correlation_trades(movement_correlations, data, scan_time)
    logger.info("Correlation trades (|r|>=%.2f): %d", 0.60, len(corr_trades))

    global_chains = []
    if is_global_mode():
        from global_index_chains import scan_global_index_chains

        global_chains = scan_global_index_chains()
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

    message = format_daily_message(
        scan_time,
        movers,
        predictions,
        global_chains,
        movement_correlations,
        corr_trades,
    )
    plain = format_plain(message)
    plain += "\n".join(format_trades_plain(corr_trades))

    os.makedirs(os.path.dirname(DAILY_OUTPUT) or ".", exist_ok=True)
    with open(DAILY_OUTPUT, "w") as fh:
        fh.write(plain)

    sent = False
    if send_telegram:
        from telegram_alerts import TelegramBot
        bot = TelegramBot()
        if bot.enabled:
            sent = bot.send_message(message)

    n_corr = log_correlation_trades(corr_trades, telegram_sent=sent)
    update_correlation_outcomes()
    write_corr_report()

    _log_scan_heartbeat(scan_time, len(corr_trades), sent)
    log_predictions(scan_time, predictions, sent)
    update_outcomes(min_age_days=1)
    write_scoreboard()
    write_tracker_report()

    logger.info(
        "Pipeline done: universe=%s focus=%d corr_trades=%d strict_preds=%d telegram=%s logged=%d",
        getattr(scan_result, "universe_size", "?"),
        len(focus_list),
        len(corr_trades),
        len(predictions),
        sent,
        n_corr,
    )
    return True, plain


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ok, text = run_pipeline(send_telegram=False)
    print(text)
