#!/usr/bin/env python3
"""Action hints from chain divergences and validated lead/lag (not auto-trades)."""
from __future__ import annotations

from typing import List

from momentum_chain import MomentumChain, ChainLink

MIN_HIT_RATE = 55.0
MIN_HIT_N = 8


def _is_divergence(focus_1d: float, link: ChainLink) -> bool:
    if abs(focus_1d) < 0.3 or abs(link.move_1d_pct) < 0.3:
        return False
    return focus_1d * link.move_1d_pct < 0


def action_hints(chain: MomentumChain) -> List[str]:
    """Short actionable lines for Telegram (entry triggers still manual)."""
    f = chain.focus
    hints: List[str] = []

    for link in chain.links:
        if link.regime_break:
            hints.append(
                f"⚠ {link.node}: correlation regime broke vs {f.ticker} — treat link as unreliable"
            )

    peers = [
        l for l in chain.links
        if l.layer == "micro" and l.corr_significant and _is_divergence(f.return_1d_pct, l)
    ]
    for p in peers[:2]:
        if p.corr_21d > 0:
            hints.append(
                f"↔ {p.node} opposite today but +corr — mean-reversion watch on {f.ticker}"
            )
        else:
            hints.append(
                f"↔ {p.node} opposite today, inverse corr — spread may be stretched"
            )

    leaders = [
        l for l in chain.links
        if l.lead_lag_days > 0
        and l.lag_hit_rate is not None
        and l.lag_hit_rate >= MIN_HIT_RATE
        and l.lag_hit_n >= MIN_HIT_N
    ]
    leaders.sort(key=lambda x: (x.lag_hit_rate or 0), reverse=True)
    for lead in leaders[:2]:
        expected = "up" if (lead.corr_21d > 0) == (lead.move_1d_pct > 0) else "down"
        if abs(lead.move_1d_pct) >= 1.5 and abs(f.return_1d_pct) < abs(lead.move_1d_pct) - 1:
            hints.append(
                f"→ {lead.node} leads ~{lead.lead_lag_days}d "
                f"(hit {lead.lag_hit_rate:.0f}%/n={lead.lag_hit_n}): "
                f"if {lead.node} holds, {f.ticker} may follow {expected} in ~{lead.lead_lag_days}d"
            )

    if f.return_1d_pct > 1.5 and f.return_5d_pct < -3:
        macro_down = [
            l for l in chain.links
            if l.layer == "macro"
            and l.lead_lag_days > 0
            and l.move_1d_pct < -1
            and (l.lag_hit_rate or 0) >= MIN_HIT_RATE
        ]
        if macro_down:
            m = macro_down[0]
            hints.append(
                f"⚡ {f.ticker} green today but 5d weak; {m.node} leads down "
                f"(hit {m.lag_hit_rate:.0f}%) — fade / tight stop if long"
            )

    return hints[:4]
