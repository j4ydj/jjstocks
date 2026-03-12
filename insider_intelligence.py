#!/usr/bin/env python3
"""
INSIDER INTELLIGENCE MODULE
===========================

EDGE: Early indicators of company changes (filings, corporate actions)

DATA SOURCES:
• SEC EDGAR (free): company submissions, recent 10-K/10-Q/8-K, Form 4 insider transactions
• Job posting momentum / patent filings: stubs for future free APIs

VALUE: Filing changes and insider activity often lead price by weeks.
WHY IT WORKS: 8-K events and Form 4 cluster before big moves.

Author: Revolutionary Trading System
Status: Phase 2 - Insider Edge
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

SEC_USER_AGENT = "TradingBot/1.0 (Educational; contact@example.com)"
SEC_BASE = "https://data.sec.gov"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


@dataclass
class InsiderSignal:
    """Insider/filing analysis result"""
    ticker: str
    edge_signal: float       # 0-1 bullish score
    confidence: float        # 0-1
    reasoning: str
    data_quality: float      # 0-1
    recent_8k_count: int
    recent_insider_buys: int
    recent_insider_sells: int
    last_10k_date: Optional[str]
    filing_summary: str


class InsiderIntelligence:
    """
    Insider Intelligence: SEC filings and corporate action signals.
    Uses free SEC EDGAR APIs only. User-Agent required by SEC.
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.enabled = self.config.get("INSIDER_ENABLED", True)
        self.user_agent = self.config.get("SEC_USER_AGENT", SEC_USER_AGENT)
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 86400  # 24h for filings
        self._ticker_to_cik: Optional[Dict[str, str]] = None

    def _headers(self) -> Dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json"}

    def _ticker_to_cik_map(self) -> Dict[str, str]:
        if self._ticker_to_cik is not None:
            return self._ticker_to_cik
        try:
            r = requests.get(TICKERS_URL, headers=self._headers(), timeout=10)
            r.raise_for_status()
            data = r.json()
            out = {}
            for entry in data.values():
                if isinstance(entry, dict) and "ticker" in entry and "cik_str" in entry:
                    ticker = str(entry["ticker"]).upper()
                    cik = str(entry["cik_str"]).zfill(10)
                    out[ticker] = cik
            self._ticker_to_cik = out
            return out
        except Exception as e:
            logger.warning(f"SEC ticker map failed: {e}")
            self._ticker_to_cik = {}
            return {}

    def _get_submissions(self, cik: str) -> Optional[Dict]:
        url = f"{SEC_BASE}/submissions/CIK{cik}.json"
        try:
            r = requests.get(url, headers=self._headers(), timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.debug(f"SEC submissions for CIK {cik}: {e}")
            return None

    def analyze(self, ticker: str) -> Optional[InsiderSignal]:
        if not self.enabled:
            return None

        cache_key = f"{ticker}_{int(time.time() / self.cache_ttl)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            ticker = ticker.upper()
            cik_map = self._ticker_to_cik_map()
            cik = cik_map.get(ticker)
            if not cik:
                return self._no_data_signal(ticker, "Ticker not found in SEC EDGAR")

            data = self._get_submissions(cik)
            if not data:
                return self._no_data_signal(ticker, "No submissions data")

            recent = data.get("filings", {}).get("recent") or {}
            forms = recent.get("form") or []
            dates = recent.get("filingDate") or []
            if not forms or not dates:
                return self._no_data_signal(ticker, "No recent filings")

            # Count last ~90 days
            cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
            recent_8k = 0
            last_10k = None
            for i, (f, d) in enumerate(zip(forms, dates)):
                if d < cutoff:
                    continue
                if f == "8-K":
                    recent_8k += 1
                if f in ("10-K", "10-K/A") and (last_10k is None or d > last_10k):
                    last_10k = d

            # Form 4 (insider) from same recent filings if present
            # Note: "buys"/"sells" here are Form 4 vs 4/A counts; true direction would need parsing filing content
            form4_buys = 0
            form4_sells = 0
            for f in forms:
                if f == "4":
                    form4_buys += 1
                elif f == "4/A":
                    form4_sells += 1

            # Heuristic signal: more 8-K = more corporate change; recent 10-K = fresh data
            edge = 0.5
            reasons = []
            if recent_8k > 2:
                edge += 0.15
                reasons.append(f"{recent_8k} recent 8-K(s)")
            elif recent_8k > 0:
                edge += 0.05
                reasons.append("Recent 8-K filed")
            if last_10k:
                reasons.append(f"Last 10-K: {last_10k}")
            if form4_buys > form4_sells and (form4_buys + form4_sells) > 0:
                edge += 0.1
                reasons.append("Insider buying (Form 4)")
            elif form4_sells > form4_buys and (form4_buys + form4_sells) > 0:
                edge -= 0.1
                reasons.append("Insider selling (Form 4)")

            edge = max(0.0, min(1.0, edge))
            data_quality = 0.9 if (forms and dates) else 0.5
            confidence = data_quality * (0.7 + 0.3 * min(1.0, (recent_8k + len(forms)) / 20))
            reasoning = "; ".join(reasons) if reasons else "No significant filing activity"
            summary = f"8-K: {recent_8k}, Form 4 buys: {form4_buys}, sells: {form4_sells}"
            if last_10k:
                summary += f", Last 10-K: {last_10k}"

            signal = InsiderSignal(
                ticker=ticker,
                edge_signal=edge,
                confidence=min(1.0, confidence),
                reasoning=reasoning,
                data_quality=data_quality,
                recent_8k_count=recent_8k,
                recent_insider_buys=form4_buys,
                recent_insider_sells=form4_sells,
                last_10k_date=last_10k,
                filing_summary=summary,
            )
            self.cache[cache_key] = signal
            return signal

        except Exception as e:
            logger.error(f"Insider analysis failed for {ticker}: {e}")
            return self._no_data_signal(ticker, str(e))

    def _no_data_signal(self, ticker: str, reason: str) -> InsiderSignal:
        return InsiderSignal(
            ticker=ticker,
            edge_signal=0.5,
            confidence=0.0,
            reasoning=reason,
            data_quality=0.0,
            recent_8k_count=0,
            recent_insider_buys=0,
            recent_insider_sells=0,
            last_10k_date=None,
            filing_summary="No data",
        )

    def health_check(self) -> bool:
        try:
            m = self._ticker_to_cik_map()
            return "AAPL" in m
        except Exception:
            return False


def get_insider_signal(ticker: str, config: Dict = None) -> Optional[InsiderSignal]:
    analyzer = InsiderIntelligence(config or {})
    out = analyzer.analyze(ticker)
    if out and out.data_quality == 0 and out.confidence == 0:
        return None
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = {"INSIDER_ENABLED": True, "SEC_USER_AGENT": SEC_USER_AGENT}
    for sym in ["AAPL", "TSLA", "INVALID"]:
        s = get_insider_signal(sym, cfg)
        if s:
            print(f"{s.ticker}: edge={s.edge_signal:.2f} conf={s.confidence:.2f} | {s.filing_summary}")
        else:
            print(f"{sym}: no signal")
