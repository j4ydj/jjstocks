#!/usr/bin/env python3
"""
SEC Filing Risk Filter — Path Less Travelled
============================================
Free, legal edge: scan latest 10-K/10-Q for risk phrases.
Only take long signals when the company's own filings don't scream "going concern" / "material weakness".

Uses SEC EDGAR only. Same User-Agent and rate-limit pattern as insider_intelligence.py.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

SEC_USER_AGENT = "TradingBot/1.0 (Educational; contact@example.com)"
SEC_BASE = "https://data.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Phrases that often appear in risky filings (going concern, material weakness, distress)
RISK_PHRASES = [
    r"going\s+concern",
    r"substantial\s+doubt",
    r"material\s+weakness",
    r"material\s+weaknesses",
    r"restructuring\s+charges?",
    r"significant\s+layoff",
    r"layoffs?\s+and",
    r"bankruptcy",
    r"default\s+on\s+(our|the)\s+debt",
    r"ability\s+to\s+continue\s+as",
    r"may\s+not\s+continue\s+as",
    r"liquidity\s+constraints?",
    r"substantial\s+doubt\s+about",
]
RISK_PATTERNS = [re.compile(p, re.I) for p in RISK_PHRASES]

# Rate limit: 10 req/sec per SEC guidance
_MIN_REQUEST_INTERVAL = 0.11
_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _headers(config: Dict) -> Dict[str, str]:
    ua = (config or {}).get("SEC_USER_AGENT", SEC_USER_AGENT)
    return {"User-Agent": ua, "Accept": "application/json"}


_ticker_to_cik: Optional[Dict[str, str]] = None


def _ticker_to_cik_map(config: Dict) -> Dict[str, str]:
    global _ticker_to_cik
    if _ticker_to_cik is not None:
        return _ticker_to_cik
    _rate_limit()
    try:
        r = requests.get(TICKERS_URL, headers=_headers(config), timeout=10)
        r.raise_for_status()
        data = r.json()
        out = {}
        for entry in data.values():
            if isinstance(entry, dict) and "ticker" in entry and "cik_str" in entry:
                ticker = str(entry["ticker"]).upper()
                cik = str(entry["cik_str"]).zfill(10)
                out[ticker] = cik
        _ticker_to_cik = out
        return out
    except Exception as e:
        logger.warning("SEC ticker map failed: %s", e)
        _ticker_to_cik = {}
        return {}


def _get_submissions(cik: str, config: Dict) -> Optional[Dict]:
    url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    _rate_limit()
    try:
        r = requests.get(url, headers=_headers(config), timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.debug("SEC submissions for CIK %s: %s", cik, e)
        return None


def _get_latest_10k_or_10q(submissions: Dict) -> Optional[Tuple[str, str, str]]:
    """Returns (accession_no_dashes, primary_doc, form_type) or None."""
    recent = submissions.get("filings", {}).get("recent") or {}
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_docs = recent.get("primaryDocument") or []
    if not all([forms, dates, accessions, primary_docs]):
        return None
    best = None
    best_date = ""
    for i, (form, date, acc, doc) in enumerate(zip(forms, dates, accessions, primary_docs)):
        if form not in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
            continue
        if not doc or not acc:
            continue
        if date > best_date:
            best_date = date
            best = (acc.replace("-", ""), doc, form)
    return best


def _fetch_filing_text(cik: str, accession_dashes_removed: str, primary_doc: str, config: Dict) -> Optional[str]:
    """Fetch primary document and return first ~150KB of text (enough for risk phrases)."""
    # Archives are served from www.sec.gov per SEC
    url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_dashes_removed}/{primary_doc}"
    _rate_limit()
    try:
        # Request as text; SEC serves HTML
        h = _headers(config).copy()
        h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        r = requests.get(url, headers=h, timeout=30)
        if r.status_code != 200:
            return None
        text = r.text
        # Limit size to avoid huge 10-Ks; 150KB is enough for risk section
        if len(text) > 200_000:
            text = text[:200_000]
        return text
    except Exception as e:
        logger.debug("Fetch filing failed %s: %s", url[:80], e)
        return None


def count_risk_phrases(text: str) -> int:
    """Count how many distinct risk phrase patterns appear in text."""
    if not text:
        return 0
    found = set()
    for pat in RISK_PATTERNS:
        if pat.search(text):
            found.add(pat.pattern)
    return len(found)


def is_clean(ticker: str, config: Optional[Dict] = None) -> Tuple[bool, str, int]:
    """
    For a ticker, fetch latest 10-K or 10-Q and check for risk phrases.
    Returns (clean: bool, form_used: str, risk_count: int).
    clean=True means we found 0 risk phrases (safe to use as long filter).
    """
    config = config or {}
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return False, "", 0

    cik_map = _ticker_to_cik_map(config)
    cik = cik_map.get(ticker)
    if not cik:
        logger.debug("No CIK for %s", ticker)
        return False, "NO_CIK", 0

    data = _get_submissions(cik, config)
    if not data:
        return False, "NO_SUBMISSIONS", 0

    latest = _get_latest_10k_or_10q(data)
    if not latest:
        return True, "NO_10K_10Q", 0  # no annual/quarterly filing to scan → treat as clean

    acc_nd, primary_doc, form_type = latest
    text = _fetch_filing_text(cik, acc_nd, primary_doc, config)
    if not text:
        return True, form_type, 0  # can't read → don't block the signal

    risk_count = count_risk_phrases(text)
    clean = risk_count == 0
    return clean, form_type, risk_count


def risk_score(ticker: str, config: Optional[Dict] = None) -> float:
    """
    Returns 0.0 (clean) to 1.0 (many risk phrases). Use for ranking/filtering.
    """
    clean, _, count = is_clean(ticker, config)
    if count == 0:
        return 0.0
    # Cap score: 3+ hits = max risk
    return min(1.0, count / 3.0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = {"SEC_USER_AGENT": SEC_USER_AGENT}
    for sym in ["AAPL", "TSLA", "GME"]:
        c, form, n = is_clean(sym, cfg)
        print(f"{sym}: clean={c} form={form} risk_phrases={n} score={risk_score(sym, cfg):.2f}")
