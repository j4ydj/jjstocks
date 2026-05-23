#!/usr/bin/env python3
"""
Unconventional edge layers — not typical retail scanner inputs.

- Wikipedia attention (retail/human curiosity before price)
- SEC filing risk (narrative distress in 10-K/10-Q)
- Macro index chain pressure (cross-asset propagation paths)
- Residual spread z (pair mispricing vs historical beta)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from pipeline_config import FADE_MODE, RESIDUAL_Z_MIN
from pipeline_filters import spread_zscore

logger = logging.getLogger(__name__)


@dataclass
class AltSignalResult:
    score: float  # 0–100 composite
    reasons: List[str] = field(default_factory=list)
    wiki_score: Optional[float] = None
    sec_clean: bool = True
    on_macro_chain: bool = False
    spread_z: Optional[float] = None


def _wiki_score(ticker: str) -> Optional[float]:
    try:
        import wikipedia_views

        return wikipedia_views.trend_score(ticker, 14)
    except Exception:
        return None


def _sec_clean(ticker: str) -> bool:
    try:
        import sec_filing_risk

        clean, _, _ = sec_filing_risk.is_clean(ticker, {})
        return bool(clean)
    except Exception:
        return True


def macro_chain_tickers(global_chains: Optional[List[Any]]) -> Set[str]:
    """ETFs/nodes appearing on hot global index chains today."""
    out: Set[str] = set()
    if not global_chains:
        return out
    for ch in global_chains:
        path = getattr(ch, "path", None) or getattr(ch, "description", "") or ""
        for part in str(path).replace("→", " ").replace("->", " ").split():
            sym = part.strip().upper()
            if sym and len(sym) <= 6:
                out.add(sym)
    return out


def score_alt_signals(
    *,
    focus: str,
    leader: str,
    direction: str,
    corr: float,
    rets: Optional[pd.DataFrame] = None,
    end_idx: Optional[int] = None,
    hit_rate: Optional[float] = None,
    global_chains: Optional[List[Any]] = None,
    playbook_ok: bool = False,
) -> AltSignalResult:
    """
    Higher score = more unconventional confirmation aligned with the trade.
    """
    reasons: List[str] = []
    score = 40.0  # base if passed hard filters elsewhere

    z = None
    if rets is not None and end_idx is not None and focus in rets.columns and leader in rets.columns:
        z = spread_zscore(rets, focus, leader, corr, end_idx)
    if z is not None:
        if FADE_MODE:
            if direction == "BUY" and z >= RESIDUAL_Z_MIN:
                score += 18
                reasons.append(f"spread z {z:+.1f} supports fade long")
            elif direction == "SHORT" and z <= -RESIDUAL_Z_MIN:
                score += 18
                reasons.append(f"spread z {z:+.1f} supports fade short")
        else:
            score += 10
            reasons.append(f"spread z {z:+.1f}")

    if playbook_ok:
        score += 25
        reasons.append("walk-forward playbook")

    if hit_rate is not None and hit_rate >= 70:
        score += min(12, (hit_rate - 70) / 3)
        reasons.append(f"pair history {hit_rate:.0f}% hit")

    wiki = _wiki_score(focus)
    if wiki is not None:
        if direction == "BUY" and wiki > 0.35:
            score += 12
            reasons.append(f"Wikipedia attention rising ({wiki:+.2f})")
        elif direction == "SHORT" and wiki < -0.35:
            score += 12
            reasons.append(f"Wikipedia attention fading ({wiki:+.2f})")
        elif direction == "BUY" and wiki < -0.5:
            score -= 15
            reasons.append("wiki cold vs long (crowd not watching yet)")
        elif direction == "SHORT" and wiki > 0.5:
            score -= 15
            reasons.append("wiki hot vs short")

    if not _sec_clean(focus):
        score -= 40
        reasons.append("SEC risk phrases in filings")
    else:
        score += 8
        reasons.append("SEC clean")

    chain_syms = macro_chain_tickers(global_chains)
    if focus.upper() in chain_syms or leader.upper() in chain_syms:
        score += 14
        reasons.append("on global macro index chain path")

    return AltSignalResult(
        score=min(100, max(0, score)),
        reasons=reasons,
        wiki_score=wiki,
        sec_clean=_sec_clean(focus),
        on_macro_chain=focus.upper() in chain_syms or leader.upper() in chain_syms,
        spread_z=z,
    )
