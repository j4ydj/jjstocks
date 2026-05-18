#!/usr/bin/env python3
"""
Actionable trade setups from chain relationships.

Only surfaces catch-up and divergence ideas that pass OOS + regime gates.
"""
from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from momentum_chain import MIN_CORR_ABS, MomentumChain, ChainLink
from trade_levels import TradeLevels, calculate_levels

MIN_OOS_HIT = float(os.getenv("MIN_OOS_HIT", "55"))
MIN_HIT_EVENTS = int(os.getenv("MIN_HIT_EVENTS", "8"))
LEADER_MOVE_MIN = float(os.getenv("LEADER_MOVE_MIN", "2.0"))
CATCHUP_GAP_MIN = float(os.getenv("CATCHUP_GAP_MIN", "1.0"))
DIVERGE_MOVE_MIN = float(os.getenv("DIVERGE_MOVE_MIN", "1.0"))
VIX_SPIKE_MAX = float(os.getenv("VIX_SPIKE_MAX", "5.0"))
MACRO_DOWN_BLOCK = float(os.getenv("MACRO_DOWN_BLOCK", "1.0"))
MIN_PEER_DV = float(os.getenv("MIN_SETUP_DOLLAR_VOL", "10000000"))


@dataclass
class TradeSetup:
    setup_type: str
    ticker: str
    direction: str
    leader: str
    thesis: str
    leader_move_1d: float
    focus_move_1d: float
    corr: float
    lag_days: int
    hit_rate: float
    hit_rate_oos: Optional[float]
    hit_n_oos: int
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    risk_pct: float = 0.0
    risk_reward: float = 0.0
    position_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _link_hit(link: ChainLink) -> Tuple[Optional[float], int]:
  """Prefer OOS hit rate when available."""
  if link.lag_hit_rate_oos is not None and link.lag_hit_n_oos >= MIN_HIT_EVENTS:
      return link.lag_hit_rate_oos, link.lag_hit_n_oos
  if link.lag_hit_rate is not None and link.lag_hit_n >= MIN_HIT_EVENTS:
      return link.lag_hit_rate, link.lag_hit_n
  return None, 0


def _valid_move(pct: float) -> bool:
    return pct == pct and abs(pct) < 50  # exclude NaN / bad ticks


def _link_passes(link: ChainLink) -> bool:
    if not _valid_move(link.move_1d_pct):
        return False
    if link.regime_break:
        return False
    if abs(link.corr_21d) < MIN_CORR_ABS:
        return False
    hit, n = _link_hit(link)
    return hit is not None and hit >= MIN_OOS_HIT and n >= MIN_HIT_EVENTS


def _macro_regime(chain: MomentumChain) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for l in chain.links:
        if l.layer == "macro":
            out[l.node.upper()] = l.move_1d_pct
    return out


def regime_allows_long(chain: MomentumChain) -> bool:
    macro = _macro_regime(chain)
    vix = macro.get("^VIX", 0.0)
    if vix > VIX_SPIKE_MAX:
        return False
    spy = macro.get("SPY", 0.0)
    qqq = macro.get("QQQ", 0.0)
    if spy < -MACRO_DOWN_BLOCK and qqq < -MACRO_DOWN_BLOCK:
        return False
    return True


def regime_allows_short(chain: MomentumChain) -> bool:
    macro = _macro_regime(chain)
    vix = macro.get("^VIX", 0.0)
    if vix > VIX_SPIKE_MAX * 1.5:
        return True
    return True


def _opposite(a: float, b: float) -> bool:
    return a * b < 0 and abs(a) >= DIVERGE_MOVE_MIN and abs(b) >= DIVERGE_MOVE_MIN


def _attach_levels(setup: TradeSetup, df: Optional[pd.DataFrame]) -> TradeSetup:
    if df is None or df.empty:
        return setup
    lv = calculate_levels(setup.ticker, setup.direction, df, conviction=4, hold_days=5)
    if not lv:
        return setup
    setup.entry_price = lv.entry_price
    setup.stop_loss = lv.stop_loss
    setup.target_price = lv.target_price
    setup.risk_pct = lv.risk_pct
    setup.risk_reward = lv.risk_reward
    setup.position_pct = lv.position_pct
    return setup


def _catch_up_setups(chain: MomentumChain) -> List[TradeSetup]:
    f = chain.focus
    setups: List[TradeSetup] = []
    candidates = [
        l for l in chain.links
        if l.layer == "micro" and _link_passes(l) and l.lead_lag_days >= 0
    ]
    candidates.sort(key=lambda x: abs(x.corr_21d), reverse=True)

    for lead in candidates[:3]:
        if abs(lead.move_1d_pct) < LEADER_MOVE_MIN:
            continue
        if abs(f.return_1d_pct) >= abs(lead.move_1d_pct) - CATCHUP_GAP_MIN:
            continue

        hit, hit_n = _link_hit(lead)
        if hit is None:
            continue

        if lead.corr_21d > 0:
            direction = "BUY" if lead.move_1d_pct > 0 else "SHORT"
        else:
            direction = "SHORT" if lead.move_1d_pct > 0 else "BUY"

        if direction == "BUY" and not regime_allows_long(chain):
            continue
        if direction == "SHORT" and not regime_allows_short(chain):
            continue

        lag_s = f"~{lead.lead_lag_days}d" if lead.lead_lag_days else "same day"
        setups.append(
            TradeSetup(
                setup_type="catch_up",
                ticker=f.ticker,
                direction=direction,
                leader=lead.node,
                thesis=(
                    f"{lead.node} {lead.move_1d_pct:+.1f}% today; {f.ticker} lagging "
                    f"({f.return_1d_pct:+.1f}%). Historically follows {lag_s} "
                    f"(OOS hit {hit:.0f}%, n={hit_n})."
                ),
                leader_move_1d=lead.move_1d_pct,
                focus_move_1d=f.return_1d_pct,
                corr=lead.corr_21d,
                lag_days=lead.lead_lag_days,
                hit_rate=lead.lag_hit_rate or hit,
                hit_rate_oos=lead.lag_hit_rate_oos,
                hit_n_oos=hit_n,
            )
        )
    return setups


def _divergence_setups(chain: MomentumChain) -> List[TradeSetup]:
    f = chain.focus
    setups: List[TradeSetup] = []
    for link in chain.links:
        if link.layer != "micro" or not _link_passes(link):
            continue
        if link.corr_21d <= 0:
            continue
        if not _opposite(f.return_1d_pct, link.move_1d_pct):
            continue

        direction = "BUY" if f.return_1d_pct < 0 else "SHORT"
        if direction == "BUY" and not regime_allows_long(chain):
            continue
        if direction == "SHORT" and not regime_allows_short(chain):
            continue

        hit, hit_n = _link_hit(link)
        if hit is None:
            continue

        setups.append(
            TradeSetup(
                setup_type="divergence",
                ticker=f.ticker,
                direction=direction,
                leader=link.node,
                thesis=(
                    f"{f.ticker} and {link.node} usually move together (r={link.corr_21d:+.2f}) "
                    f"but diverged today ({f.return_1d_pct:+.1f}% vs {link.move_1d_pct:+.1f}%). "
                    f"Mean-reversion watch (OOS hit {hit:.0f}%)."
                ),
                leader_move_1d=link.move_1d_pct,
                focus_move_1d=f.return_1d_pct,
                corr=link.corr_21d,
                lag_days=link.lead_lag_days,
                hit_rate=link.lag_hit_rate or hit,
                hit_rate_oos=link.lag_hit_rate_oos,
                hit_n_oos=hit_n,
            )
        )
    return setups[:2]


def _fade_risk_setup(chain: MomentumChain) -> List[TradeSetup]:
    f = chain.focus
    if f.return_1d_pct <= 1.5 or f.return_5d_pct >= -3:
        return []

    macro_down = [
        l for l in chain.links
        if l.layer == "macro"
        and l.move_1d_pct < -1.0
        and _link_passes(l)
        and l.lead_lag_days >= 0
    ]
    if not macro_down:
        return []

    lead = macro_down[0]
    hit, hit_n = _link_hit(lead)
    if hit is None:
        return []

    return [
        TradeSetup(
            setup_type="fade_risk",
            ticker=f.ticker,
            direction="SHORT",
            leader=lead.node,
            thesis=(
                f"{f.ticker} up {f.return_1d_pct:+.1f}% today but 5d {f.return_5d_pct:+.1f}%; "
                f"{lead.node} weak ({lead.move_1d_pct:+.1f}%). Risk-off fade (OOS hit {hit:.0f}%)."
            ),
            leader_move_1d=lead.move_1d_pct,
            focus_move_1d=f.return_1d_pct,
            corr=lead.corr_21d,
            lag_days=lead.lead_lag_days,
            hit_rate=lead.lag_hit_rate or hit,
            hit_rate_oos=lead.lag_hit_rate_oos,
            hit_n_oos=hit_n,
        )
    ]


def find_setups(
    chain: MomentumChain,
    price_cache: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[TradeSetup]:
    """All actionable setups for one focus chain."""
    price_cache = price_cache or {}
    raw: List[TradeSetup] = []
    raw.extend(_catch_up_setups(chain))
    raw.extend(_divergence_setups(chain))
    raw.extend(_fade_risk_setup(chain))

    best: Dict[Tuple[str, str, str], TradeSetup] = {}
    for s in raw:
        df = price_cache.get(s.ticker)
        if df is None:
            df = price_cache.get(s.ticker.upper())
        s = _attach_levels(s, df)
        key = (s.setup_type, s.ticker, s.direction)
        prev = best.get(key)
        score = s.hit_rate_oos or s.hit_rate or 0
        if prev is None or score > (prev.hit_rate_oos or prev.hit_rate or 0):
            best[key] = s
    return list(best.values())


def find_all_setups(
    chains: List[MomentumChain],
    price_cache: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[TradeSetup]:
    setups: List[TradeSetup] = []
    for chain in chains:
        setups.extend(find_setups(chain, price_cache))
    setups.sort(key=lambda s: (s.hit_rate_oos or s.hit_rate or 0), reverse=True)
    return setups
