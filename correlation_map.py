#!/usr/bin/env python3
"""
Extensive multi-horizon correlation map — not limited to predefined chains.

Builds a full pairwise view (multiple time windows), lead/lag on the best horizon,
high-correlation clusters, and multi-step paths (A → B → C).
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from chain_stats import corr_pvalue, lead_lag_hit_rate, macro_bucket
from momentum_chain import (
    MACRO_NODES,
    daily_returns,
    lead_lag_corr,
    load_scan_universe,
    min_dollar_volume,
    rank_by_volatility,
)

logger = logging.getLogger(__name__)

HORIZONS = [int(x) for x in os.getenv("CORR_HORIZONS", "5,21,60,120").split(",")]
MIN_EDGE_CORR = float(os.getenv("CORR_MAP_MIN_CORR", "0.40"))
MIN_LIQUIDITY = float(os.getenv("CORR_MAP_MIN_DV", "10000000"))
MAX_PATH_DEPTH = int(os.getenv("CORR_MAP_PATH_DEPTH", "3"))
PATH_MIN_CORR = float(os.getenv("CORR_MAP_PATH_CORR", "0.45"))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAP_JSON = os.path.join(DATA_DIR, "correlation_map.json")
EDGES_CSV = os.path.join(DATA_DIR, "correlation_edges.csv")
PATHS_CSV = os.path.join(DATA_DIR, "correlation_paths.csv")


@dataclass
class HorizonStat:
    days: int
    corr: float
    lag: int = 0
    hit_rate: Optional[float] = None
    hit_n: int = 0
    pvalue: float = 1.0


@dataclass
class MapEdge:
    source: str
    target: str
    target_layer: str  # equity | macro
    best_horizon: int
    best_corr: float
    relation: str
    lag_days: int
    hit_rate: Optional[float] = None
    hit_n: int = 0
    horizons: Dict[str, HorizonStat] = field(default_factory=dict)
    target_move_1d: float = 0.0
    target_move_5d: float = 0.0


@dataclass
class MapPath:
    focus: str
    nodes: List[str]
    hops: int
    min_corr: float
    avg_corr: float
    description: str


@dataclass
class CompanySituationMap:
    scan_time: str
    universe_size: int
    nodes_in_matrix: int
    focus_tickers: List[str]
    edges: List[MapEdge]
    paths: List[MapPath]
    clusters: List[Dict[str, object]]
    node_snapshot: Dict[str, Dict[str, float]]


def _bulk_download(tickers: List[str], period: str = "2y") -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    chunk = 80
    for i in range(0, len(tickers), chunk):
        batch = tickers[i : i + chunk]
        try:
            raw = yf.download(
                batch,
                period=period,
                group_by="ticker",
                progress=False,
                threads=True,
                auto_adjust=True,
            )
            if raw is None or raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                for t in raw.columns.get_level_values(0).unique():
                    try:
                        df = raw[t].copy()
                        if "Close" in df.columns and len(df) > max(HORIZONS) + 10:
                            out[str(t).upper()] = df.dropna(subset=["Close"])
                    except Exception:
                        pass
            elif len(batch) == 1 and "Close" in raw.columns:
                out[batch[0].upper()] = raw.dropna(subset=["Close"])
        except Exception as e:
            logger.warning("Download chunk failed: %s", e)
    return out


def _returns_matrix(data: Dict[str, pd.DataFrame], min_bars: int = 60) -> pd.DataFrame:
    """Delegate to returns_align (6mo scans need min_bars < 130)."""
    from returns_align import build_returns_matrix

    return build_returns_matrix(data, min_bars=min_bars)


def _moves(df: pd.DataFrame) -> Tuple[float, float]:
    c = df["Close"]
    m1 = (c.iloc[-1] / c.iloc[-2] - 1) * 100 if len(c) >= 2 else 0.0
    m5 = (c.iloc[-1] / c.iloc[-6] - 1) * 100 if len(c) >= 6 else 0.0
    return round(m1, 2), round(m5, 2)


def _relation(c: float) -> str:
    if c >= 0.25:
        return "together"
    if c <= -0.25:
        return "inverse"
    return "weak"


def _horizon_stats(
    rets: pd.DataFrame,
    source: str,
    target: str,
    days: int,
) -> Optional[HorizonStat]:
    if source not in rets.columns or target not in rets.columns:
        return None
    sub = rets[[source, target]].tail(days + 5).dropna()
    if len(sub) < max(8, days // 2):
        return None
    c = float(sub[source].corr(sub[target]))
    if np.isnan(c):
        return None
    lag = 0
    hit, hit_n = None, 0
    if days >= 21:
        lag = lead_lag_corr(sub[source], sub[target])[1]
        hit, hit_n = lead_lag_hit_rate(sub[source], sub[target], lag, c, min_events=6)
    return HorizonStat(
        days=days,
        corr=round(c, 4),
        lag=lag,
        hit_rate=hit,
        hit_n=hit_n,
        pvalue=round(corr_pvalue(c, len(sub)), 4),
    )


def _edges_for_focus(
    focus: str,
    rets: pd.DataFrame,
    data: Dict[str, pd.DataFrame],
    min_corr: float,
) -> List[MapEdge]:
    edges: List[MapEdge] = []
    if focus not in rets.columns:
        return edges

    for target in rets.columns:
        if target == focus:
            continue
        hstats: Dict[str, HorizonStat] = {}
        best_h, best_c = 0, 0.0
        for h in HORIZONS:
            st = _horizon_stats(rets, focus, target, h)
            if st is None:
                continue
            hstats[str(h)] = st
            if abs(st.corr) > abs(best_c):
                best_c, best_h = st.corr, h

        if abs(best_c) < min_corr:
            continue

        st_best = hstats.get(str(best_h))
        lag = st_best.lag if st_best else 0
        hit = st_best.hit_rate if st_best else None
        hit_n = st_best.hit_n if st_best else 0
        layer = "macro" if target in MACRO_NODES else "equity"
        m1, m5 = 0.0, 0.0
        if target in data:
            m1, m5 = _moves(data[target])

        edges.append(
            MapEdge(
                source=focus,
                target=target,
                target_layer=layer,
                best_horizon=best_h,
                best_corr=round(best_c, 4),
                relation=_relation(best_c),
                lag_days=lag,
                hit_rate=hit,
                hit_n=hit_n,
                horizons=hstats,
                target_move_1d=m1,
                target_move_5d=m5,
            )
        )

    edges.sort(key=lambda e: abs(e.best_corr), reverse=True)
    return edges


def _clusters_from_edges(edges: List[MapEdge], min_corr: float = 0.65) -> List[List[str]]:
    """Connected components among strong equity-equity links."""
    adj: Dict[str, Set[str]] = defaultdict(set)
    nodes: Set[str] = set()
    for e in edges:
        if e.target_layer != "equity" or abs(e.best_corr) < min_corr:
            continue
        nodes.add(e.source)
        nodes.add(e.target)
        adj[e.source].add(e.target)
        adj[e.target].add(e.source)

    seen: Set[str] = set()
    clusters: List[List[str]] = []
    for n in nodes:
        if n in seen:
            continue
        comp: List[str] = []
        q = deque([n])
        seen.add(n)
        while q:
            u = q.popleft()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        if len(comp) >= 2:
            clusters.append(sorted(comp))
    clusters.sort(key=len, reverse=True)
    return clusters


def _multi_step_paths(focus: str, edges: List[MapEdge], max_depth: int) -> List[MapPath]:
    """BFS paths focus → … → leaf using edges above PATH_MIN_CORR."""
    adj: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for e in edges:
        if abs(e.best_corr) < PATH_MIN_CORR:
            continue
        adj[e.source].append((e.target, e.best_corr))

    paths: List[MapPath] = []
    queue: deque = deque([(focus, [focus], [])])
    seen_paths: Set[str] = set()

    while queue:
        node, chain, corrs = queue.popleft()
        if len(chain) > max_depth:
            continue
        for nxt, c in adj.get(node, []):
            if nxt in chain:
                continue
            new_chain = chain + [nxt]
            new_corrs = corrs + [c]
            key = "→".join(new_chain)
            if len(new_chain) >= 2 and key not in seen_paths:
                seen_paths.add(key)
                paths.append(
                    MapPath(
                        focus=focus,
                        nodes=new_chain,
                        hops=len(new_chain) - 1,
                        min_corr=round(min(abs(x) for x in new_corrs), 3),
                        avg_corr=round(float(np.mean([abs(x) for x in new_corrs])), 3),
                        description=" → ".join(new_chain),
                    )
                )
            if len(new_chain) < max_depth:
                queue.append((nxt, new_chain, new_corrs))

    paths.sort(key=lambda p: (p.hops, -p.min_corr))
    return paths[:80]


class CorrelationMapBuilder:
    def __init__(
        self,
        universe: Optional[List[str]] = None,
        focus_top_n: int = 25,
        universe_cap: int = 350,
        min_corr: float = MIN_EDGE_CORR,
    ):
        self.universe = universe or load_scan_universe()
        self.focus_top_n = focus_top_n
        self.universe_cap = universe_cap
        self.min_corr = min_corr

    def build(self) -> CompanySituationMap:
        tickers = self.universe[: self.universe_cap]
        macros = [m for m in MACRO_NODES if m not in tickers]
        tickers = list(dict.fromkeys(tickers + macros))

        logger.info("Downloading %d symbols (2y)...", len(tickers))
        data = _bulk_download(tickers, period="2y")
        logger.info("Downloaded %d symbols", len(data))

        rets = _returns_matrix(data)
        logger.info("Returns matrix: %d days × %d symbols", len(rets), len(rets.columns))

        top, _ = rank_by_volatility(
            [t for t in rets.columns if t in data and t not in MACRO_NODES],
            self.focus_top_n,
            prefetched=data,
        )
        focus_list = [p.ticker for p in top]
        if not focus_list:
            focus_list = list(rets.columns[: self.focus_top_n])

        all_edges: List[MapEdge] = []
        all_paths: List[MapPath] = []
        all_clusters: List[Dict[str, object]] = []

        for focus in focus_list:
            f_edges = _edges_for_focus(focus, rets, data, self.min_corr)
            all_edges.extend(f_edges)
            paths = _multi_step_paths(focus, f_edges, MAX_PATH_DEPTH)
            all_paths.extend(paths)
            for i, cl in enumerate(_clusters_from_edges(f_edges)):
                if len(cl) >= 2:
                    all_clusters.append({"focus": focus, "id": i, "members": cl})

        snapshot: Dict[str, Dict[str, float]] = {}
        for sym in list(rets.columns)[:400]:
            if sym in data:
                m1, m5 = _moves(data[sym])
                snapshot[sym] = {
                    "move_1d": m1,
                    "move_5d": m5,
                    "price": round(float(data[sym]["Close"].iloc[-1]), 2),
                }

        return CompanySituationMap(
            scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            universe_size=len(self.universe),
            nodes_in_matrix=len(rets.columns),
            focus_tickers=focus_list,
            edges=all_edges,
            paths=all_paths,
            clusters=all_clusters,
            node_snapshot=snapshot,
        )


def _serialize_map(m: CompanySituationMap) -> dict:
    def edge_dict(e: MapEdge) -> dict:
        d = asdict(e)
        d["horizons"] = {k: asdict(v) for k, v in e.horizons.items()}
        return d

    return {
        "scan_time": m.scan_time,
        "universe_size": m.universe_size,
        "nodes_in_matrix": m.nodes_in_matrix,
        "focus_tickers": m.focus_tickers,
        "horizons_used": HORIZONS,
        "min_corr": MIN_EDGE_CORR,
        "edges": [edge_dict(e) for e in m.edges],
        "paths": [asdict(p) for p in m.paths],
        "clusters": m.clusters,
        "node_snapshot": m.node_snapshot,
    }


def save_map(m: CompanySituationMap) -> Tuple[str, str, str]:
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = _serialize_map(m)
    with open(MAP_JSON, "w") as fh:
        json.dump(payload, fh, indent=2)

    edge_rows = []
    for e in m.edges:
        row = {
            "source": e.source,
            "target": e.target,
            "layer": e.target_layer,
            "best_horizon": e.best_horizon,
            "best_corr": e.best_corr,
            "relation": e.relation,
            "lag_days": e.lag_days,
            "hit_rate": e.hit_rate,
            "hit_n": e.hit_n,
            "move_1d": e.target_move_1d,
        }
        for h in HORIZONS:
            st = e.horizons.get(str(h))
            row[f"corr_{h}d"] = st.corr if st else None
            row[f"lag_{h}d"] = st.lag if st else None
        edge_rows.append(row)

    pd.DataFrame(edge_rows).to_csv(EDGES_CSV, index=False)
    pd.DataFrame([asdict(p) for p in m.paths]).to_csv(PATHS_CSV, index=False)
    return MAP_JSON, EDGES_CSV, PATHS_CSV


def write_report(m: CompanySituationMap, path: str) -> None:
    lines = [
        "# Correlation map (multi-horizon, multi-step)",
        "",
        f"> Generated: **{m.scan_time}**",
        f"> Matrix: **{m.nodes_in_matrix}** symbols × horizons **{HORIZONS}** d",
        f"> Focus names: **{len(m.focus_tickers)}** | Edges (|r|≥{MIN_EDGE_CORR}): **{len(m.edges)}** | Paths: **{len(m.paths)}**",
        "",
        "## Focus tickers",
        "",
        ", ".join(m.focus_tickers),
        "",
        "## Largest correlation clusters (equity)",
        "",
    ]
    big = sorted(m.clusters, key=lambda c: len(c.get("members", [])), reverse=True)[:15]
    for c in big:
        mem = c.get("members", [])
        lines.append(f"- **{c.get('focus', '?')}** ({len(mem)} names): {', '.join(mem[:12])}{'…' if len(mem)>12 else ''}")

    lines.extend(["", "## Multi-step paths (examples)", ""])
    for p in m.paths[:40]:
        lines.append(
            f"- **{p.focus}** [{p.hops} hop] {p.description} "
            f"(min |r| {p.min_corr}, avg |r| {p.avg_corr})"
        )

    lines.extend(["", "## Top direct links per focus (best horizon)", ""])
    by_focus: Dict[str, List[MapEdge]] = defaultdict(list)
    for e in m.edges:
        by_focus[e.source].append(e)

    for focus in m.focus_tickers[:12]:
        edges = by_focus[focus][:8]
        if not edges:
            continue
        lines.append(f"\n### {focus}\n")
        lines.append("| Target | Layer | Best H | r | Lag | 5d | 21d | 60d | 120d |")
        lines.append("|--------|-------|--------|---|-----|-----|-----|-----|------|")
        for e in edges:
            def ch(h):
                st = e.horizons.get(str(h))
                return f"{st.corr:+.2f}" if st else "—"
            lines.append(
                f"| {e.target} | {e.target_layer} | {e.best_horizon}d | {e.best_corr:+.2f} | "
                f"{e.lag_days:+d} | {ch(5)} | {ch(21)} | {ch(60)} | {ch(120)} |"
            )

    lines.extend([
        "",
        "## Files",
        "",
        f"- `{MAP_JSON}` — full graph JSON",
        f"- `{EDGES_CSV}` — all edges (spreadsheet)",
        f"- `{PATHS_CSV}` — multi-hop paths",
        "",
        "```bash",
        "python build_correlation_map.py",
        "```",
        "",
    ])
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
