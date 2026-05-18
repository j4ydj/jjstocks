#!/usr/bin/env python3
"""
Simple chain alerts for Telegram.

One message: what moved, what usually follows, prices and % stamped with time.
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
from chain_actions import action_hints
from chain_stats import dedupe_macro_links

MOVE_MIN_PCT = float(os.getenv("PING_MOVE_MIN_PCT", "1.5"))
DEFAULT_TOP_N = int(os.getenv("MOMENTUM_TOP_N", "8"))
MIN_PEER_CORR = float(os.getenv("MIN_PEER_CORR", str(MIN_CORR_ABS)))
MIN_MACRO_CORR = float(os.getenv("MIN_MACRO_CORR", str(MIN_CORR_ABS)))


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
    """21d return correlation tendency (not guaranteed same day)."""
    if corr >= 0.25:
        return "together"
    if corr <= -0.25:
        return "inverse"
    return "weak"


def _today_alignment(focus_1d: float, peer_1d: float) -> str:
    """Whether today's moves point the same way."""
    if abs(focus_1d) < 0.3 or abs(peer_1d) < 0.3:
        return "flat today"
    if focus_1d * peer_1d > 0:
        return "same way today"
    return "opposite today"


def _lag_timing(lag: int) -> str:
    """Human label from lead_lag_days (+N = peer leads focus)."""
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
    if link.lag_hit_rate is not None and link.lag_hit_n >= 8:
        parts.append(f"fwd {link.lag_hit_rate:.0f}%")
    if link.regime_break:
        parts.append("regime⚠")
    return f" ({', '.join(parts)})" if parts else ""


def _peer_line(peer, focus_1d: float) -> str:
    rel = _corr_relation(peer.corr_21d)
    today = _today_alignment(focus_1d, peer.move_1d_pct)
    timing = _lag_timing(peer.lead_lag_days)
    corr_s = f"r{CORR_LOOKBACK_DAYS} {peer.corr_21d:+.2f}"
    return (
        f"  • <b>{_esc(peer.node)}</b>  {_fmt_price(peer.last_price)}  "
        f"{_fmt_pct(peer.move_1d_pct)} today — {corr_s}, {rel}; "
        f"{timing}; {today}{_quality_suffix(peer)}"
    )


def chains_with_moves(result: MomentumScanResult) -> List[MomentumChain]:
    """Focus names with a meaningful 1-day move."""
    out = [c for c in result.chains if abs(c.focus.return_1d_pct) >= MOVE_MIN_PCT]
    out.sort(key=lambda c: abs(c.focus.return_1d_pct), reverse=True)
    return out


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
        lines.append(f"Linked names ({CORR_LOOKBACK_DAYS}d r≥{MIN_PEER_CORR:.2f}; today may differ):")
        for p in peers[:5]:
            if p.node.upper() in shown:
                continue
            shown.add(p.node.upper())
            lines.append(_peer_line(p, f.return_1d_pct))

    macro = [
        l for l in chain.links
        if l.layer == "macro" and abs(l.corr_21d) >= MIN_MACRO_CORR
    ]
    leaders = dedupe_macro_links(macro)
    leaders.sort(key=lambda x: abs(x.move_1d_pct), reverse=True)
    if leaders:
        lines.append("Market (1 per macro bucket):")
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

    hints = action_hints(chain)
    if hints:
        lines.append("Action hints:")
        for h in hints:
            lines.append(f"  {_esc(h)}")

    return lines


def format_telegram_ping(result: MomentumScanResult) -> str:
    """Single HTML message for Telegram."""
    ts = result.scan_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    movers = chains_with_moves(result)

    lines = [
        "<b>Chain alert</b>",
        f"<i>{_esc(ts)}</i>",
        f"<i>corr window {CORR_LOOKBACK_DAYS}d · min |r| {MIN_CORR_ABS:.2f}</i>",
        "",
    ]

    if not movers:
        lines.append("No big 1-day moves in the top volatile list right now.")
        lines.append("")
        lines.append("Watching:")
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


def format_plain_ping(result: MomentumScanResult) -> str:
    """Plain text for logs / terminal."""
    import re
    html = format_telegram_ping(result)
    text = re.sub(r"<[^>]+>", "", html)
    return text


def run_scan(top_n: Optional[int] = None) -> MomentumScanResult:
    n = top_n if top_n is not None else DEFAULT_TOP_N
    return MomentumChainFinder(top_n=n).scan()


def scan_and_notify(send_telegram: bool = True) -> Tuple[MomentumScanResult, str, bool]:
    from chain_actions import action_hints
    from signal_log import log_scan

    result = run_scan()
    message = format_telegram_ping(result)
    hints_map = {}
    for c in chains_with_moves(result):
        h = action_hints(c)
        if h:
            hints_map[c.focus.ticker.upper()] = h
    try:
        log_scan(result, hints_map)
    except Exception:
        pass
    sent = False
    if send_telegram:
        from telegram_alerts import TelegramBot
        bot = TelegramBot()
        if bot.enabled:
            sent = bot.send_message(message)
    return result, message, sent


if __name__ == "__main__":
    result, msg, sent = scan_and_notify(send_telegram=False)
    print(format_plain_ping(result))
    print(f"\n[telegram={'sent' if sent else 'dry run'}]")
