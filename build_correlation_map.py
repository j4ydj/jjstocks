#!/usr/bin/env python3
"""Build the full correlation map. Run: python build_correlation_map.py"""
from __future__ import annotations

import argparse
import logging
import sys

from correlation_map import (
    CorrelationMapBuilder,
    MAP_JSON,
    EDGES_CSV,
    PATHS_CSV,
    save_map,
    write_report,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> int:
    p = argparse.ArgumentParser(description="Build multi-horizon correlation map")
    p.add_argument("--focus-top", type=int, default=25, help="Volatile names to expand fully")
    p.add_argument("--universe-cap", type=int, default=350, help="Max symbols in matrix")
    p.add_argument("--min-corr", type=float, default=0.40, help="Min |r| to keep an edge")
    p.add_argument("--report", default="CORRELATION_MAP.md")
    args = p.parse_args()

    builder = CorrelationMapBuilder(
        focus_top_n=args.focus_top,
        universe_cap=args.universe_cap,
        min_corr=args.min_corr,
    )
    print("Building correlation map (this may take several minutes)...")
    m = builder.build()
    j, e, pa = save_map(m)
    write_report(m, args.report)
    print(f"Done: {len(m.edges)} edges, {len(m.paths)} paths, {len(m.clusters)} cluster records")
    print(f"  {j}")
    print(f"  {e}")
    print(f"  {pa}")
    print(f"  {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
