"""Auto-discover chain peers from sector/industry and theme tags."""
import logging
from functools import lru_cache
from typing import Dict, List, Optional, Set

import yfinance as yf

logger = logging.getLogger(__name__)

CRYPTO_ADJACENT = {"COIN", "MSTR", "MARA", "RIOT", "HUT", "CLSK", "HOOD", "SQ"}
SPACE_THEME = {"RKLB", "ASTS", "LUNR", "SPCE", "PL", "RDW", "BKSY", "SPIR"}
AI_THEME = {"NVDA", "AMD", "SMCI", "PLTR", "IONQ", "SOUN", "BBAI", "AI", "PATH"}

THEME_MAP: Dict[str, Set[str]] = {}
for t in CRYPTO_ADJACENT:
    THEME_MAP.setdefault("crypto", set()).add(t)
for t in SPACE_THEME:
    THEME_MAP.setdefault("space", set()).add(t)
for t in AI_THEME:
    THEME_MAP.setdefault("ai", set()).add(t)

PEER_POOL = list({
    *CRYPTO_ADJACENT, *SPACE_THEME, *AI_THEME,
    "NVDA", "AMD", "INTC", "TSM", "SMH", "PLTR", "SOFI", "HOOD", "RIVN", "LCID",
})


@lru_cache(maxsize=256)
def _ticker_meta(ticker: str) -> tuple:
    try:
        info = yf.Ticker(ticker).info or {}
        return (
            (info.get("sector") or "").strip().lower(),
            (info.get("industry") or "").strip().lower(),
        )
    except Exception:
        return ("", "")


def themes_for(ticker: str) -> List[str]:
    t = ticker.upper()
    out = []
    for name, members in THEME_MAP.items():
        if t in members:
            out.append(name)
    return out


def peers_from_industry(ticker: str, universe: Optional[List[str]] = None, limit: int = 8) -> List[str]:
    """Same-industry names from compact peer pool (cached yfinance)."""
    sector, industry = _ticker_meta(ticker)
    if not industry and not sector:
        return []
    pool = list(dict.fromkeys((universe or []) + PEER_POOL))
    matches: List[str] = []
    for sym in pool:
        if sym.upper() == ticker.upper():
            continue
        s2, i2 = _ticker_meta(sym)
        if industry and i2 == industry:
            matches.append(sym)
        elif sector and s2 == sector:
            matches.append(sym)
        if len(matches) >= limit:
            break
    return matches[:limit]


def peers_from_themes(ticker: str, limit: int = 6) -> List[str]:
    t = ticker.upper()
    found: List[str] = []
    for theme in themes_for(t):
        for sym in THEME_MAP.get(theme, []):
            if sym != t and sym not in found:
                found.append(sym)
    return found[:limit]


def macro_extras_for(ticker: str) -> List[str]:
    """Extra macro symbols (e.g. BTC for crypto names)."""
    extras: List[str] = []
    if ticker.upper() in CRYPTO_ADJACENT or "crypto" in themes_for(ticker):
        extras.append("BTC-USD")
    return extras


def discover_peers(ticker: str, universe: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Returns upstream_micro and downstream_micro suggestions."""
    industry = peers_from_industry(ticker, universe=universe, limit=6)
    thematic = peers_from_themes(ticker, limit=6)
    micro = list(dict.fromkeys(industry + thematic))[:10]
    return {
        "upstream_micro": micro[:6],
        "downstream_micro": micro[6:10],
        "upstream_macro": macro_extras_for(ticker),
    }
