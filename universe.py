"""Ticker universe for volatility ranking (S&P 500 + high-beta extras)."""
import os
from typing import List


def load_scan_universe() -> List[str]:
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


UNIVERSE = load_scan_universe()
