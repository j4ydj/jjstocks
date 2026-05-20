"""Ticker universe for scans — US (default) or global multi-index."""
import os
from typing import List


def _load_us_universe() -> List[str]:
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "sp500_symbols.txt")
    tickers: List[str] = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                s = line.strip().upper()
                if s and not s.startswith("#"):
                    tickers.append(s)
    extras = [
        "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI", "GME", "AMC",
        "PLTR", "COIN", "MSTR", "HOOD", "SOFI", "UPST", "SMCI", "ARM",
        "JOBY", "ACHR", "RGTI",
    ]
    for t in extras:
        if t not in tickers:
            tickers.append(t)
    return list(dict.fromkeys(tickers))


def load_scan_universe() -> List[str]:
    mode = os.getenv("SCAN_UNIVERSE", "global").strip().lower()
    if mode in ("global", "world", "all", "1", "true", "yes"):
        from global_indexes import load_global_universe
        return load_global_universe()
    return _load_us_universe()


def universe_label() -> str:
    from global_indexes import is_global_mode
    return "global" if is_global_mode() else "us"


UNIVERSE = load_scan_universe()
