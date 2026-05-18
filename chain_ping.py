#!/usr/bin/env python3
"""
Chain alerts for Telegram.

Modes (ALERT_MODE):
  actionable — only send when catch-up / divergence / fade setups pass filters (default)
  full       — always send relationship map for big movers
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional, Tuple

from momentum_chain import (
    CORR_LOOKBACK_DAYS,
    MIN_CORR_ABS,
    MomentumChain,
    MomentumChainFinder,
    MomentumScanResult,
)
from chain_stats import dedupe_macro_links
from chain_setups import TradeSetup, find_all_setups

MOVE_MIN_PCT = float(os.getenv("PING_MOVE_MIN_PCT", "1.5"))
DEFAULT_TOP_N = int(os.getenv("MOMENTUM_TOP_N", "8"))
MIN_PEER_CORR = float(os.getenv("MIN_PEER_CORR", str(MIN_CORR_ABS)))
MIN_MACRO_CORR = float(os.getenv("MIN_MACRO_CORR", str(MIN_CORR_ABS)))
ALERT_MODE = os.getenv("ALERT_MODE", "actionable").lower()


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_price(p: float) -> str:
    if p <= 0:
        return "—"
    if p >= 1000:
        return f"${p:,.2f}"
    if p >= 1:
        return f"${p:.2f}"
    return f"${p:.4f}"


def _fmt_pct(v: float) -> str:
    return f"{v:+.1f}%"


def _corr_relation(corr: float) -> str:
    if corr >= 0.25:
        return "together"
    if corr <= -0.25:
        return "inverse"
    return "weak"


def _today_alignment(focus_1d: float, peer_1d: float) -> str:
    if abs(focus_1d) < 0.3 or abs(peer_1d) < 0.3:
        return "flat today"
    if focus_1d * peer_1d > 0:
        return "same way today"
    return "opposite today"


def _lag_timing(lag: int) -> str:
    if lag > 0:
        return f"leads ~{lag}d"
    if lag < 0:
        return f"lags ~{-lag}d"
    return "same day"


def _quality_suffix(link) -> str:
    parts = []
    if link.corr_significant:
        parts.append(f"p&lt;0.05 n={link.sample_n}")
    elif link.sample_n:
        parts.append(f"n={link.sample_n}")
    if link.lag_hit_rate_oos is not None and link.lag_hit_n_oos >= 8:
        parts.append(f"OOS {link.lag_hit_rate_oos:.0f}%")
    elif link.lag_hit_rate is not None and link.lag_hit_n >= 8:
        parts.append(f"fwd {link.lag_hit_rate:.0f}%")
    if link.regime_break:
        parts.append("regime⚠")
    return f" ({', '.join(parts)})" if parts else ""


def _peer_line(peer, focus_1d: float) -> str:
    rel = _corr_relation(peer.corr_21d)
    today = _today_alignment(focus_1d, peer.move_1d_pct)
    timing = _lag_timing(peer.lead_lag_days)
    return (
        f"  • <b>{_esc(peer.node)}</b>  {_fmt_price(peer.last_price)}  "
        f"{_fmt_pct(peer.move_1d_pct)} today — r{CORR_LOOKBACK_DAYS} {peer.corr_21d:+.2f}, {rel}; "
        f"{timing}; {today}{_quality_suffix(peer)}"
    )


def chains_with_moves(result: MomentumScanResult) -> List[MomentumChain]:
    out = [c for c in result.chains if abs(c.focus.return_1d_pct) >= MOVE_MIN_PCT]
    out.sort(key=lambda c: abs(c.focus.return_1d_pct), reverse=True)
    return out


def format_setup_block(s: TradeSetup) -> List[str]:
    emoji = "📈" if s.direction == "BUY" else "📉"
    type_label = s.setup_type.replace("_", " ").title()
    oos = f"{s.hit_rate_oos:.0f}%" if s.hit_rate_oos is not None else f"{s.hit_rate:.0f}%"
    lines = [
        f"{emoji} <b>{s.direction} {s.ticker}</b>  <i>{type_label}</i>",
        f"  {_esc(s.thesis)}",
        f"  Leader: <b>{_esc(s.leader)}</b> {_fmt_pct(s.leader_move_1d)} · "
        f"r={s.corr:+.2f} · OOS hit {oos}",
    ]
    if s.entry_price > 0:
        lines.append(
            f"  Entry {_fmt_price(s.entry_price)} · Stop {_fmt_price(s.stop_loss)} · "
            f"Target {_fmt_price(s.target_price)} · Risk {s.risk_pct:.1f}% · "
            f"R:R {s.risk_reward:.1f} · Size ~{s.position_pct:.0f}% port"
        )
    else:
        lines.append("  (levels unavailable — check chart)")
    return lines


def format_actionable_ping(result: MomentumScanResult, setups: List[TradeSetup]) -> str:
    ts = result.scan_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "<b>Trade setups</b>",
        f"<i>{_esc(ts)}</i>",
        f"<i>{len(setups)} idea(s) · r≥{MIN_CORR_ABS:.2f} · OOS hit≥{os.getenv('MIN_OOS_HIT', '55')}%</i>",
        "",
    ]
    for i, s in enumerate(setups[:5]):
        if i > 0:
            lines.append("")
        lines.extend(format_setup_block(s))
    return "\n".join(lines)


def format_chain_block(chain: MomentumChain) -> List[str]:
    f = chain.focus
    lines = [
        f"<b>{_esc(f.ticker)}</b>  {_fmt_price(f.last_price)}  "
        f"<b>{_fmt_pct(f.return_1d_pct)}</b> today  ({_fmt_pct(f.return_5d_pct)} over 5 days)",
    ]

    peers = [
        l for l in chain.links
        if l.layer == "micro" and abs(l.corr_21d) >= MIN_PEER_CORR and l.node != f.ticker
    ]
    peers.sort(key=lambda x: abs(x.corr_21d), reverse=True)
    shown = {f.ticker.upper()}
    if peers:
        lines.append(f"Linked names ({CORR_LOOKBACK_DAYS}d r≥{MIN_PEER_CORR:.2f}):")
        for p in peers[:5]:
            if p.node.upper() in shown:
                continue
            shown.add(p.node.upper())
            lines.append(_peer_line(p, f.return_1d_pct))

    macro = [l for l in chain.links if l.layer == "macro" and abs(l.corr_21d) >= MIN_MACRO_CORR]
    leaders = dedupe_macro_links(macro)
    leaders.sort(key=lambda x: abs(x.move_1d_pct), reverse=True)
    if leaders:
        lines.append("Market (1 per bucket):")
        for m in leaders[:3]:
            if m.node.upper() in shown:
                continue
            shown.add(m.node.upper())
            lines.append(
                f"  • {_esc(m.node)}  {_fmt_price(m.last_price)}  {_fmt_pct(m.move_1d_pct)} today — "
                f"r{CORR_LOOKBACK_DAYS} {m.corr_21d:+.2f}, {_corr_relation(m.corr_21d)}; "
                f"{_lag_timing(m.lead_lag_days)}; "
                f"{_today_alignment(f.return_1d_pct, m.move_1d_pct)}{_quality_suffix(m)}"
            )
    return lines


def format_telegram_ping(result: MomentumScanResult) -> str:
    ts = result.scan_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    movers = chains_with_moves(result)
    lines = [
        "<b>Chain alert</b>",
        f"<i>{_esc(ts)}</i>",
        f"<i>corr {CORR_LOOKBACK_DAYS}d · min |r| {MIN_CORR_ABS:.2f}</i>",
        "",
    ]
    if not movers:
        lines.append("No big 1-day moves in the top volatile list right now.")
        for c in result.chains[:3]:
            f = c.focus
            lines.append(
                f"  • {f.ticker}  {_fmt_price(f.last_price)}  {_fmt_pct(f.return_1d_pct)} today"
            )
    else:
        for i, chain in enumerate(movers[:4]):
            if i > 0:
                lines.append("")
            lines.extend(format_chain_block(chain))
    return "\n".join(lines)


def format_plain_ping(result: MomentumScanResult, message: Optional[str] = None) -> str:
    import re
    html = message or format_telegram_ping(result)
    return re.sub(r"<[^>]+>", "", html)


def run_scan(top_n: Optional[int] = None) -> MomentumScanResult:
    n = top_n if top_n is not None else DEFAULT_TOP_N
    return MomentumChainFinder(top_n=n).scan()


def scan_and_notify(send_telegram: bool = True) -> Tuple[MomentumScanResult, str, bool]:
    from trade_tracker import log_proposed_trades, update_outcomes

    result = run_scan()
    mover_chains = chains_with_moves(result)
    setups = find_all_setups(mover_chains, result.price_cache)

    if ALERT_MODE == "full":
        message = format_telegram_ping(result)
        send = send_telegram
    else:
        if setups:
            message = format_actionable_ping(result, setups)
            send = send_telegram
        else:
            message = ""
            send = False

    sent = False
    if send and message:
        from telegram_alerts import TelegramBot
        bot = TelegramBot()
        if bot.enabled:
            sent = bot.send_message(message)

    try:
        log_proposed_trades(result, setups, telegram_sent=sent, alert_mode=ALERT_MODE)
        update_outcomes(min_age_days=1)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Trade log failed: %s", e)

    return result, message, sent


if __name__ == "__main__":
    result, msg, sent = scan_and_notify(send_telegram=False)
    setups = find_all_setups(chains_with_moves(result), result.price_cache)
    print(f"Mode={ALERT_MODE} setups={len(setups)}")
    if msg:
        print(format_plain_ping(result, msg))
    else:
        print("(no message — no setups passed filters)")
    print(f"\n[telegram={'sent' if sent else 'skipped'}]")
