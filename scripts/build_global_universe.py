#!/usr/bin/env python3
"""Print merged global universe stats (constituents + index ETFs)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from global_indexes import INDEX_REGISTRY, GLOBAL_INDEX_ETFS, build_membership, load_global_universe


def main() -> None:
    u = load_global_universe()
    m = build_membership()
    print(f"Global universe: {len(u)} tickers")
    print(f"Index ETFs (macro nodes): {len(GLOBAL_INDEX_ETFS)}")
    print(f"Indexes in registry: {len(INDEX_REGISTRY)}")
    print(f"Tickers with index membership: {len(m)}")
    by_region: dict = {}
    for idx in INDEX_REGISTRY:
        by_region[idx.region] = by_region.get(idx.region, 0) + 1
    print("Regions:", by_region)


if __name__ == "__main__":
    main()
