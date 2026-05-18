#!/usr/bin/env python3
"""Correlation statistics, macro dedup buckets, lead/lag forward validation."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# One macro "vote" per bucket — avoids ARKK + SMH + QQQ counting as 3 signals
MACRO_BUCKETS: Dict[str, List[str]] = {
    "risk_on_growth": ["ARKK", "QQQ", "XLK", "SMH", "IWM", "XLC"],
    "broad_equity": ["SPY"],
    "rates": ["TLT"],
    "dollar": ["UUP"],
    "volatility": ["^VIX"],
    "credit": ["HYG"],
    "oil": ["USO"],
    "gold": ["GLD"],
    "energy_sector": ["XLE"],
    "tech_sector": ["XLK"],
    "financials": ["XLF"],
    "healthcare": ["XLV"],
    "biotech": ["XBI"],
    "semis": ["SMH"],
}

_NODE_TO_BUCKET: Dict[str, str] = {}
for bucket, nodes in MACRO_BUCKETS.items():
    for n in nodes:
        _NODE_TO_BUCKET[n.upper()] = bucket


def macro_bucket(node: str) -> Optional[str]:
    return _NODE_TO_BUCKET.get(node.upper())


def corr_pvalue(r: float, n: int) -> float:
    """Two-tailed p-value for Pearson r (normal approx, reliable for n >= 30)."""
    if n < 4:
        return 1.0
    r = max(-0.9999, min(0.9999, r))
    t = abs(r) * math.sqrt((n - 2) / max(1e-12, 1.0 - r * r))
    from math import erfc, sqrt
    return min(1.0, max(0.0, 2.0 * erfc(t / sqrt(2))))


def corr_significant(r: float, n: int, alpha: float = 0.05) -> bool:
    return n >= 20 and abs(r) >= 0.25 and corr_pvalue(r, n) < alpha


def aligned_returns(focus_rets: pd.Series, node_rets: pd.Series) -> pd.DataFrame:
    return pd.concat([focus_rets.rename("f"), node_rets.rename("n")], axis=1).dropna()


def lead_lag_hit_rate(
    focus_rets: pd.Series,
    node_rets: pd.Series,
    lag: int,
    corr: float,
    move_thresh: float = 0.01,
    min_events: int = 8,
) -> Tuple[Optional[float], int]:
    """
    Forward test: when the leader moves materially, does focus move as correlation implies?

    lag > 0: node leads → node move on t, focus on t+lag
    lag < 0: focus leads → focus move on t, node on t+|lag| (test from focus side)
    lag == 0: same-day directional agreement on |move| days
    """
    df = aligned_returns(focus_rets, node_rets)
    if len(df) < lag + min_events + 2:
        return None, 0

    positive_corr = corr >= 0
    hits = 0
    total = 0

    if lag > 0:
        for i in range(len(df) - lag):
            node_ret = float(df["n"].iloc[i])
            focus_ret = float(df["f"].iloc[i + lag])
            if abs(node_ret) < move_thresh:
                continue
            predicted_up = node_ret > 0 if positive_corr else node_ret < 0
            if (focus_ret > 0) == predicted_up:
                hits += 1
            total += 1
    elif lag < 0:
        k = -lag
        for i in range(len(df) - k):
            focus_ret = float(df["f"].iloc[i])
            node_ret = float(df["n"].iloc[i + k])
            if abs(focus_ret) < move_thresh:
                continue
            predicted_up = focus_ret > 0 if positive_corr else focus_ret < 0
            if (node_ret > 0) == predicted_up:
                hits += 1
            total += 1
    else:
        for i in range(len(df)):
            nr = float(df["n"].iloc[i])
            fr = float(df["f"].iloc[i])
            if abs(nr) < move_thresh and abs(fr) < move_thresh:
                continue
            if abs(nr) >= move_thresh:
                predicted_up = nr > 0 if positive_corr else nr < 0
                if (fr > 0) == predicted_up:
                    hits += 1
                total += 1

    if total < min_events:
        return None, total
    return round(100.0 * hits / total, 1), total


def dedupe_macro_links(links: List, max_per_bucket: int = 1) -> List:
    """Keep strongest |corr| per macro bucket."""
    macro = [l for l in links if getattr(l, "layer", None) == "macro"]
    other = [l for l in links if getattr(l, "layer", None) != "macro"]
    macro.sort(key=lambda x: abs(x.corr_21d), reverse=True)
    seen: Dict[str, int] = {}
    kept = []
    for l in macro:
        b = macro_bucket(l.node) or l.node
        if seen.get(b, 0) >= max_per_bucket:
            continue
        seen[b] = seen.get(b, 0) + 1
        kept.append(l)
    return other + kept


def correlation_regime_break(
    focus_rets: pd.Series,
    node_rets: pd.Series,
    short_window: int = 10,
    long_window: int = 60,
) -> bool:
    """True when recent correlation diverges sharply from longer window (regime shift)."""
    if len(focus_rets) < long_window or len(node_rets) < long_window:
        return False
    df = aligned_returns(focus_rets.tail(long_window), node_rets.tail(long_window))
    if len(df) < long_window:
        return False
    r_long = float(df["f"].corr(df["n"]))
    r_short = float(df["f"].tail(short_window).corr(df["n"].tail(short_window)))
    if np.isnan(r_long) or np.isnan(r_short):
        return False
    return abs(r_short - r_long) > 0.45 and (r_long * r_short < 0 or abs(r_short) < 0.2)
