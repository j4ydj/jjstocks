#!/usr/bin/env python3
"""Cross-index correlation chains among global benchmark ETFs."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd

from correlation_map import _multi_step_paths, _returns_matrix
from global_indexes import GLOBAL_INDEX_ETFS
from momentum_chain import _bulk_download, lead_lag_corr

logger = logging.getLogger(__name__)

MIN_CORR = float(__import__("os").getenv("GLOBAL_INDEX_MIN_CORR", "0.52"))
MAX_PATHS = int(__import__("os").getenv("GLOBAL_INDEX_MAX_PATHS", "12"))


@dataclass
class GlobalIndexChain:
    path: str
    min_corr: float
    avg_corr: float
    hops: int
    lead_etf: str
    lag_etf: str
    lag_days: int


def _edges_among_etfs(rets: pd.DataFrame, min_corr: float) -> list:
    etfs = [c for c in rets.columns if c in GLOBAL_INDEX_ETFS]
    edges = []
    for src in etfs:
        for tgt in etfs:
            if src == tgt:
                continue
            sub = rets[[src, tgt]].dropna()
            if len(sub) < 40:
                continue
            c = float(sub[src].corr(sub[tgt]))
            if np.isnan(c) or abs(c) < min_corr:
                continue
            lag = lead_lag_corr(sub[src], sub[tgt])[1]

            class _E:
                pass

            o = _E()
            o.source, o.target = src, tgt
            o.best_corr, o.target_layer = c, "index_etf"
            edges.append(o)
    return edges


def scan_global_index_chains(
    min_corr: float = MIN_CORR,
    period: str = "1y",
) -> List[GlobalIndexChain]:
    """Pairwise + multi-hop chains across ~35 world index ETFs."""
    tickers = list(GLOBAL_INDEX_ETFS.keys())
    logger.info("Global index chain scan: %d ETF proxies", len(tickers))
    data = _bulk_download(tickers, period=period)
    rets = _returns_matrix(data, min_bars=60)
    if rets.empty or len(rets.columns) < 5:
        logger.warning("Insufficient ETF data for global index chains")
        return []

    all_paths = []
    etf_cols = [c for c in rets.columns if c in GLOBAL_INDEX_ETFS]
    pe = _edges_among_etfs(rets, min_corr)
    for focus in etf_cols:
        for p in _multi_step_paths(focus, pe, max_depth=4):
            if p.hops >= 1 and len(p.nodes) >= 2:
                all_paths.append(p)

    seen = set()
    out: List[GlobalIndexChain] = []
    for p in sorted(all_paths, key=lambda x: (-x.hops, -x.min_corr)):
        key = tuple(p.nodes)
        if key in seen or len(key) < 2:
            continue
        seen.add(key)
        lead, lag = p.nodes[0], p.nodes[-1]
        sub = rets[[lead, lag]].dropna()
        lag_d = lead_lag_corr(sub[lead], sub[lag])[1] if len(sub) >= 20 else 0
        out.append(
            GlobalIndexChain(
                path=" → ".join(p.nodes),
                min_corr=p.min_corr,
                avg_corr=p.avg_corr,
                hops=p.hops,
                lead_etf=lead,
                lag_etf=lag,
                lag_days=lag_d,
            )
        )
        if len(out) >= MAX_PATHS:
            break

    logger.info("Global index chains found: %d", len(out))
    return out


def format_global_chains_html(chains: List[GlobalIndexChain], scan_time: str) -> str:
    if not chains:
        return ""
    lines = ["", "<b>Global index chains</b>", f"<i>{scan_time}</i>"]
    for c in chains[:8]:
        lag_s = f", lag {c.lag_days}d" if c.lag_days else ""
        lines.append(
            f"  • <b>{c.path}</b>  (r≥{c.min_corr:.2f}, {c.hops} hop{lag_s})"
        )
    return "\n".join(lines)


def format_global_chains_plain(chains: List[GlobalIndexChain]) -> str:
    if not chains:
        return ""
    lines = ["Global index chains:"]
    for c in chains[:8]:
        lines.append(f"  {c.path}  (r>={c.min_corr:.2f}, {c.hops} hops)")
    return "\n".join(lines)
