"""
Global stock index registry — ETFs + constituent lists for cross-market scans.

Set SCAN_UNIVERSE=global on Railway/local to use the merged world universe.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

_BASE = os.path.dirname(os.path.abspath(__file__))
_INDEX_DIR = os.path.join(_BASE, "data", "indexes")


@dataclass(frozen=True)
class IndexDef:
    id: str
    name: str
    region: str
    etf: str  # liquid Yahoo proxy for the index
    symbol_file: str


# Major benchmarks — ETF is the tradeable node for index-to-index chains
INDEX_REGISTRY: List[IndexDef] = [
    IndexDef("sp500", "S&P 500", "US", "SPY", "sp500_symbols.txt"),
    IndexDef("nasdaq100", "Nasdaq-100", "US", "QQQ", "nasdaq100.txt"),
    IndexDef("dow", "Dow Jones", "US", "DIA", "dow30.txt"),
    IndexDef("russell2000", "Russell 2000", "US", "IWM", "russell2000_top.txt"),
    IndexDef("ftse100", "FTSE 100", "UK", "EWU", "ftse100.txt"),
    IndexDef("dax", "DAX", "EU", "EWG", "dax40.txt"),
    IndexDef("cac40", "CAC 40", "EU", "EWQ", "cac40.txt"),
    IndexDef("eurostoxx50", "Euro Stoxx 50", "EU", "FEZ", "eurostoxx50.txt"),
    IndexDef("nikkei225", "Nikkei 225", "JP", "EWJ", "nikkei225.txt"),
    IndexDef("hang_seng", "Hang Seng", "HK", "EWH", "hang_seng.txt"),
    IndexDef("csi300", "CSI 300", "CN", "ASHR", "csi300.txt"),
    IndexDef("asx200", "ASX 200", "AU", "EWA", "asx200.txt"),
    IndexDef("tsx60", "S&P/TSX 60", "CA", "EWC", "tsx60.txt"),
    IndexDef("bovespa", "Bovespa", "BR", "EWZ", "bovespa.txt"),
    IndexDef("kospi", "KOSPI", "KR", "EWY", "kospi.txt"),
    IndexDef("sensex", "Nifty / India", "IN", "INDA", "sensex.txt"),
    IndexDef("msci_em", "MSCI Emerging", "EM", "EEM", "msci_em.txt"),
    IndexDef("msci_eafe", "MSCI EAFE", "DM_EX_US", "EFA", "msci_eafe.txt"),
    IndexDef("msci_world", "MSCI World", "GLOBAL", "URTH", "msci_world_etfs.txt"),
]

# Always-on nodes for macro / cross-index correlation (Yahoo symbols)
GLOBAL_INDEX_ETFS: Dict[str, str] = {
    "SPY": "US S&P 500",
    "QQQ": "US Nasdaq-100",
    "DIA": "US Dow",
    "IWM": "US Russell 2000",
    "VTI": "US total market",
    "EFA": "Developed ex-US",
    "EEM": "Emerging markets",
    "VEA": "Developed markets",
    "VWO": "Emerging (Vanguard)",
    "EWJ": "Japan",
    "EWH": "Hong Kong",
    "FXI": "China large-cap",
    "ASHR": "China A-shares",
    "EWG": "Germany",
    "EWU": "UK",
    "EWQ": "France",
    "FEZ": "Eurozone",
    "EWA": "Australia",
    "EWC": "Canada",
    "EWZ": "Brazil",
    "EWY": "South Korea",
    "INDA": "India",
    "EWT": "Taiwan",
    "EWS": "Singapore",
    "EZA": "South Africa",
    "EIDO": "Indonesia",
    "EPHE": "Philippines",
    "THD": "Thailand",
    "VNM": "Vietnam",
    "URTH": "MSCI World",
    "ACWI": "All country world",
    "TLT": "US long bonds",
    "UUP": "US dollar",
    "GLD": "Gold",
    "USO": "Oil",
    "HYG": "High yield credit",
    "^VIX": "US equity vol",
    "XLK": "US tech sector",
    "XLF": "US financials",
    "XLE": "US energy",
}


def _read_symbol_file(filename: str) -> List[str]:
    path = filename if os.path.isabs(filename) else os.path.join(_INDEX_DIR, filename)
    if not os.path.exists(path):
        # sp500 lives at repo root
        alt = os.path.join(_BASE, filename)
        path = alt if os.path.exists(alt) else path
    if not os.path.exists(path):
        return []
    out: List[str] = []
    with open(path) as fh:
        for line in fh:
            s = line.strip().upper()
            if s and not s.startswith("#"):
                out.append(s)
    return out


def load_index_symbols(index_id: str) -> List[str]:
    for idx in INDEX_REGISTRY:
        if idx.id == index_id:
            syms = _read_symbol_file(idx.symbol_file)
            if idx.etf and idx.etf not in syms:
                syms = [idx.etf] + syms
            return syms
    return []


def load_global_universe() -> List[str]:
    """Merged constituents + all index ETF proxies (deduped)."""
    seen: Set[str] = set()
    ordered: List[str] = []
    for etf in GLOBAL_INDEX_ETFS:
        if etf not in seen:
            seen.add(etf)
            ordered.append(etf)
    for idx in INDEX_REGISTRY:
        for sym in load_index_symbols(idx.id):
            if sym not in seen:
                seen.add(sym)
                ordered.append(sym)
    extras = [
        "RKLB", "LUNR", "ASTS", "IONQ", "PLTR", "COIN", "MSTR", "TSM", "ASML",
        "NVO", "SAP", "BABA", "TCEHY", "TM", "SONY", "NVS", "AZN", "SHEL",
    ]
    for t in extras:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def build_membership() -> Dict[str, List[str]]:
    """ticker -> list of index ids."""
    m: Dict[str, List[str]] = {}
    for idx in INDEX_REGISTRY:
        for sym in load_index_symbols(idx.id):
            m.setdefault(sym, []).append(idx.id)
    return m


_MEMBERSHIP: Optional[Dict[str, List[str]]] = None


def ticker_indexes(ticker: str) -> List[str]:
    global _MEMBERSHIP
    if _MEMBERSHIP is None:
        _MEMBERSHIP = build_membership()
    return _MEMBERSHIP.get(ticker.upper(), [])


def correlation_candidates(
    focus: str,
    all_columns: List[str],
    *,
    max_cols: int = 500,
) -> List[str]:
    """
    Columns to test for leader/lag vs focus — global macro ETFs + same-index peers.
    Keeps prediction pass tractable on ~1k+ symbol matrices.
    """
    focus = focus.upper()
    want: Set[str] = set(GLOBAL_INDEX_ETFS.keys())
    want.update(all_columns)  # will trim below

    membership = ticker_indexes(focus)
    for idx_id in membership:
        for sym in load_index_symbols(idx_id)[:100]:
            want.add(sym)

    # All index ETFs + international listings present in matrix
    for col in all_columns:
        cu = col.upper()
        if cu in GLOBAL_INDEX_ETFS:
            want.add(col)
            continue
        if any(cu.endswith(s) for s in (".L", ".DE", ".PA", ".AS", ".MI", ".HK", ".T", ".AX", ".TO", ".NS", ".BO", ".SA")):
            want.add(col)
        elif membership:
            for idx_id in membership:
                if cu in {s.upper() for s in load_index_symbols(idx_id)[:120]}:
                    want.add(col)
                    break

    ordered = [c for c in all_columns if c in want]
    if len(ordered) > max_cols:
        ordered = ordered[:max_cols]
    return ordered if ordered else list(all_columns)[:max_cols]


def is_global_mode() -> bool:
    return os.getenv("SCAN_UNIVERSE", "global").strip().lower() in (
        "global",
        "world",
        "all",
        "1",
        "true",
        "yes",
    )
