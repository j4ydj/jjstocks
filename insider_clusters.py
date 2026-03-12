#!/usr/bin/env python3
"""
INSIDER CLUSTER BUYS
====================
EDGE: Multiple insiders buying open-market shares in a short window = strong conviction.
DATA: SEC EDGAR Form 4 filings (free, requires User-Agent).
WHY:  A single insider buy could be noise.  3+ executives buying within 30 days
      means the people who know the company best think it's undervalued.
"""

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import requests

logger = logging.getLogger(__name__)

SEC_USER_AGENT = "TradingBot/1.0 (Educational; contact@example.com)"
SEC_BASE = "https://data.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

DEFAULT_CONFIG = {
    "ENABLED": True,
    "SEC_USER_AGENT": SEC_USER_AGENT,
    "MIN_CLUSTER_SIZE": 2,        # distinct insiders buying in window
    "CLUSTER_WINDOW_DAYS": 60,
    "MIN_DOLLAR_VALUE": 10_000,   # minimum total $ purchased
}


@dataclass
class InsiderTransaction:
    filer_name: str
    title: str
    date: str
    shares: float
    price: float
    value: float
    acquire_dispose: str   # "A" = acquired, "D" = disposed


@dataclass
class InsiderClusterSignal:
    ticker: str
    signal: str             # "CLUSTER_BUY", "CLUSTER_SELL", "MIXED", "NO_DATA"
    cluster_buys: int       # distinct insiders buying
    cluster_sells: int
    total_buy_value: float
    total_sell_value: float
    confidence: float       # 0-1
    transactions: List[InsiderTransaction] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


# --- CIK lookup cache ---
_cik_cache: Dict[str, str] = {}
_cik_loaded = False


def _headers(config: dict) -> Dict[str, str]:
    ua = config.get("SEC_USER_AGENT", SEC_USER_AGENT)
    return {"User-Agent": ua, "Accept": "application/json"}


def _load_cik_map(config: dict):
    global _cik_cache, _cik_loaded
    if _cik_loaded:
        return
    try:
        r = requests.get(TICKERS_URL, headers=_headers(config), timeout=10)
        r.raise_for_status()
        data = r.json()
        for entry in data.values():
            if isinstance(entry, dict) and "ticker" in entry and "cik_str" in entry:
                tk = str(entry["ticker"]).upper()
                cik = str(entry["cik_str"]).zfill(10)
                _cik_cache[tk] = cik
        _cik_loaded = True
    except Exception as e:
        logger.warning("SEC ticker map failed: %s", e)


def _get_recent_form4(cik: str, config: dict) -> List[dict]:
    """Fetch recent Form 4 filing accession numbers from SEC EDGAR."""
    url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=_headers(config), timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.debug("SEC submissions for CIK %s: %s", cik, e)
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    window = config.get("CLUSTER_WINDOW_DAYS", 60)
    cutoff = (datetime.utcnow() - timedelta(days=window)).strftime("%Y-%m-%d")

    filings = []
    for i, (form, date, acc, doc) in enumerate(zip(forms, dates, accessions, primary_docs)):
        if form not in ("4", "4/A"):
            continue
        if date < cutoff:
            continue
        filings.append({
            "form": form,
            "date": date,
            "accession": acc.replace("-", ""),
            "doc": doc,
            "cik": cik,
        })
        if len(filings) >= 20:
            break
    return filings


def _parse_form4_xml(cik: str, accession: str, doc: str, config: dict) -> List[InsiderTransaction]:
    """Attempt to parse a Form 4 XML filing for transaction details."""
    url = f"{SEC_BASE}/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc}"
    try:
        r = requests.get(url, headers=_headers(config), timeout=10)
        if r.status_code != 200:
            return []
    except Exception:
        return []

    txns = []
    try:
        root = ET.fromstring(r.content)
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        filer_name = ""
        filer_title = ""
        rpt = root.find(f".//{ns}reportingOwner")
        if rpt is not None:
            rid = rpt.find(f"{ns}reportingOwnerId")
            if rid is not None:
                n = rid.find(f"{ns}rptOwnerName")
                if n is not None and n.text:
                    filer_name = n.text.strip()
            rel = rpt.find(f"{ns}reportingOwnerRelationship")
            if rel is not None:
                for tag in ("officerTitle", "isOfficer", "isDirector"):
                    el = rel.find(f"{ns}{tag}")
                    if el is not None and el.text:
                        if tag == "officerTitle":
                            filer_title = el.text.strip()
                            break
                        elif tag == "isDirector" and el.text.strip() == "1":
                            filer_title = "Director"

        for txn in root.findall(f".//{ns}nonDerivativeTransaction"):
            ad_el = txn.find(f".//{ns}transactionAcquiredDisposedCode/{ns}value")
            ad = ad_el.text.strip() if ad_el is not None and ad_el.text else ""
            shares_el = txn.find(f".//{ns}transactionAmounts/{ns}transactionShares/{ns}value")
            price_el = txn.find(f".//{ns}transactionAmounts/{ns}transactionPricePerShare/{ns}value")
            date_el = txn.find(f".//{ns}transactionDate/{ns}value")

            shares = float(shares_el.text) if shares_el is not None and shares_el.text else 0
            price = float(price_el.text) if price_el is not None and price_el.text else 0
            date_str = date_el.text.strip() if date_el is not None and date_el.text else ""

            # Skip option exercises / automatic plans where price is 0
            code_el = txn.find(f".//{ns}transactionCoding/{ns}transactionCode")
            code = code_el.text.strip() if code_el is not None and code_el.text else ""
            # P = open-market purchase, S = open-market sale (these are what we want)
            # M = option exercise, G = gift, etc. — skip these
            if code not in ("P", "S"):
                continue

            txns.append(InsiderTransaction(
                filer_name=filer_name,
                title=filer_title,
                date=date_str,
                shares=shares,
                price=price,
                value=round(shares * price, 2),
                acquire_dispose="A" if code == "P" else "D",
            ))
    except Exception as e:
        logger.debug("Form 4 parse error: %s", e)

    return txns


def analyze_insider_cluster(ticker: str, config: dict = None) -> Optional[InsiderClusterSignal]:
    """Detect insider buy/sell clusters for a ticker."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if not cfg.get("ENABLED", True):
        return None

    _load_cik_map(cfg)
    ticker = ticker.upper()
    cik = _cik_cache.get(ticker)
    if not cik:
        return InsiderClusterSignal(
            ticker=ticker, signal="NO_DATA", cluster_buys=0, cluster_sells=0,
            total_buy_value=0, total_sell_value=0, confidence=0,
            reasons=["Ticker not in SEC EDGAR"],
        )

    filings = _get_recent_form4(cik, cfg)
    if not filings:
        return InsiderClusterSignal(
            ticker=ticker, signal="NO_DATA", cluster_buys=0, cluster_sells=0,
            total_buy_value=0, total_sell_value=0, confidence=0,
            reasons=["No recent Form 4 filings"],
        )

    all_txns: List[InsiderTransaction] = []
    seen_accessions = set()
    for f in filings[:10]:  # limit API calls
        if f["accession"] in seen_accessions:
            continue
        seen_accessions.add(f["accession"])
        txns = _parse_form4_xml(cik, f["accession"], f["doc"], cfg)
        all_txns.extend(txns)
        time.sleep(0.12)  # SEC rate limit: 10 req/sec

    if not all_txns:
        return InsiderClusterSignal(
            ticker=ticker, signal="NO_DATA", cluster_buys=0, cluster_sells=0,
            total_buy_value=0, total_sell_value=0, confidence=0,
            reasons=["Form 4 filings found but no open-market transactions"],
        )

    buyers = {}
    sellers = {}
    total_buy_val = 0.0
    total_sell_val = 0.0

    for t in all_txns:
        if t.acquire_dispose == "A":
            buyers[t.filer_name] = buyers.get(t.filer_name, 0) + t.value
            total_buy_val += t.value
        else:
            sellers[t.filer_name] = sellers.get(t.filer_name, 0) + t.value
            total_sell_val += t.value

    n_buyers = len(buyers)
    n_sellers = len(sellers)
    reasons = []

    min_cluster = cfg["MIN_CLUSTER_SIZE"]
    min_dollar = cfg["MIN_DOLLAR_VALUE"]

    if n_buyers >= min_cluster and total_buy_val >= min_dollar:
        signal = "CLUSTER_BUY"
        confidence = min(1.0, (n_buyers / 5) * 0.5 + (total_buy_val / 500_000) * 0.5)
        reasons.append(f"{n_buyers} insiders buying (${total_buy_val:,.0f})")
        top_buyer = max(buyers.items(), key=lambda x: x[1])
        reasons.append(f"Largest: {top_buyer[0]} ${top_buyer[1]:,.0f}")
    elif n_sellers >= min_cluster and total_sell_val >= min_dollar:
        signal = "CLUSTER_SELL"
        confidence = min(1.0, (n_sellers / 5) * 0.5 + (total_sell_val / 500_000) * 0.5)
        reasons.append(f"{n_sellers} insiders selling (${total_sell_val:,.0f})")
    elif n_buyers > 0 and n_sellers > 0:
        signal = "MIXED"
        confidence = 0.2
        reasons.append(f"{n_buyers} buyers, {n_sellers} sellers")
    else:
        signal = "NO_DATA"
        confidence = 0.0
        reasons.append("No meaningful insider activity")

    return InsiderClusterSignal(
        ticker=ticker,
        signal=signal,
        cluster_buys=n_buyers,
        cluster_sells=n_sellers,
        total_buy_value=round(total_buy_val, 2),
        total_sell_value=round(total_sell_val, 2),
        confidence=round(min(1.0, confidence), 3),
        transactions=all_txns,
        reasons=reasons,
    )


def scan_insider_universe(tickers: List[str], config: dict = None) -> List[InsiderClusterSignal]:
    """Scan tickers for insider clusters, return actionable ones sorted by confidence."""
    results = []
    for tk in tickers:
        sig = analyze_insider_cluster(tk, config)
        if sig and sig.signal in ("CLUSTER_BUY", "CLUSTER_SELL"):
            results.append(sig)
        time.sleep(0.2)
    results.sort(key=lambda s: s.confidence, reverse=True)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sample = ["AAPL", "SOFI", "NVDA", "CRWD", "TSLA"]
    for s in scan_insider_universe(sample):
        print(f"  {s.ticker:6s}  {s.signal:14s}  buyers={s.cluster_buys}  "
              f"buy_val=${s.total_buy_value:,.0f}  conf={s.confidence:.2f}  "
              f"| {'; '.join(s.reasons[:2])}")
