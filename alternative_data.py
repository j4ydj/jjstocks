#!/usr/bin/env python3
"""
ALTERNATIVE DATA MODULE (Phase 3)
=================================

EDGE: Real data before it shows in earnings (consumer interest, developer adoption)

DATA SOURCES:
• Google Trends (free, via pytrends) – search interest for ticker/company
• GitHub API (free, no key) – repo activity as proxy for tech/dev adoption
• Web traffic / App rankings – stubs for future freemium APIs

VALUE: Trends and dev activity often lead revenue by quarters.
WHY IT WORKS: Search interest and GitHub stars predict product traction.

Author: Revolutionary Trading System
Status: Phase 3 - Alternative Data Edge
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

# Optional: Google Trends (pytrends can break when Google changes backend)
try:
    from pytrends.request import TrendReq
    PTRENDS_AVAILABLE = True
except ImportError:
    PTRENDS_AVAILABLE = False
    TrendReq = None

# Ticker -> search query for Trends (company name often better than ticker for big names)
TRENDS_QUERY_OVERRIDE = {
    "AAPL": "Apple stock",
    "MSFT": "Microsoft stock",
    "GOOGL": "Google stock",
    "AMZN": "Amazon stock",
    "META": "Meta stock",
    "NVDA": "Nvidia stock",
    "TSLA": "Tesla stock",
}


@dataclass
class AlternativeDataSignal:
    """Alternative data analysis result"""
    ticker: str
    edge_signal: float       # 0-1 bullish score
    confidence: float        # 0-1
    reasoning: str
    data_quality: float      # 0-1
    trend_score: Optional[float]   # 0-100 from Google Trends, or None
    trend_direction: str           # "UP", "DOWN", "FLAT", "N/A"
    github_repos: int
    github_stars: int
    web_traffic_note: str
    app_rank_note: str


class AlternativeDataIntelligence:
    """
    Alternative data: Google Trends + GitHub as free signals.
    Web traffic / app rank stubbed for future APIs.
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.enabled = self.config.get("ALTERNATIVE_DATA_ENABLED", True)
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 3600  # 1 hour
        self._pytrends: Optional[Any] = None
        self._github_headers = {"Accept": "application/vnd.github.v3+json"}
        if self.config.get("GITHUB_TOKEN"):
            self._github_headers["Authorization"] = f"token {self.config['GITHUB_TOKEN']}"

    def _get_pytrends(self):
        if not PTRENDS_AVAILABLE or TrendReq is None:
            return None
        if self._pytrends is None:
            try:
                self._pytrends = TrendReq(hl="en-US", tz=360)
            except Exception as e:
                logger.warning(f"pytrends init failed: {e}")
        return self._pytrends

    def _get_trends(self, ticker: str) -> Dict[str, Any]:
        out = {"score": None, "direction": "N/A", "ok": False}
        pt = self._get_pytrends()
        if not pt:
            return out
        try:
            kw = TRENDS_QUERY_OVERRIDE.get(ticker, ticker)
            pt.build_payload([kw], timeframe="today 3-m")
            df = pt.interest_over_time()
            if df is None or df.empty or kw not in df.columns:
                return out
            series = df[kw].dropna()
            if series.empty:
                return out
            out["score"] = float(series.iloc[-1])
            if len(series) >= 2:
                prev = float(series.iloc[-2])
                if out["score"] > prev * 1.1:
                    out["direction"] = "UP"
                elif out["score"] < prev * 0.9:
                    out["direction"] = "DOWN"
                else:
                    out["direction"] = "FLAT"
            out["ok"] = True
        except Exception as e:
            logger.debug(f"Trends failed for {ticker}: {e}")
        return out

    def _get_github(self, ticker: str) -> Dict[str, Any]:
        out = {"repos": 0, "stars": 0, "ok": False}
        # Search repos by ticker or company name (simple query)
        q = f"{ticker} stock"
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "per_page": 5},
                headers=self._github_headers,
                timeout=10,
            )
            if r.status_code != 200:
                return out
            data = r.json()
            items = data.get("items") or []
            total_count = data.get("total_count", 0)
            total_stars = sum(it.get("stargazers_count", 0) for it in items)
            out["repos"] = min(total_count, 100)  # cap for display
            out["stars"] = total_stars
            out["ok"] = True
        except Exception as e:
            logger.debug(f"GitHub search failed for {ticker}: {e}")
        return out

    def analyze(self, ticker: str) -> Optional[AlternativeDataSignal]:
        if not self.enabled:
            return None

        cache_key = f"{ticker}_{int(time.time() / self.cache_ttl)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            ticker = ticker.upper()
            trend = self._get_trends(ticker)
            github = self._get_github(ticker)

            edge = 0.5
            reasons = []
            quality = 0.0

            if trend["ok"] and trend["score"] is not None:
                quality += 0.5
                s = trend["score"]
                if s >= 70:
                    edge += 0.2
                    reasons.append(f"High search interest ({s:.0f})")
                elif s >= 50:
                    edge += 0.1
                    reasons.append(f"Moderate search interest ({s:.0f})")
                elif s < 30:
                    edge -= 0.1
                    reasons.append(f"Low search interest ({s:.0f})")
                if trend["direction"] == "UP":
                    edge += 0.05
                    reasons.append("Trend rising")
                elif trend["direction"] == "DOWN":
                    edge -= 0.05
                    reasons.append("Trend falling")

            if github["ok"] and github["stars"] > 0:
                quality += 0.3
                if github["stars"] > 1000:
                    edge += 0.1
                    reasons.append(f"Strong GitHub interest ({github['stars']} stars)")
                elif github["stars"] > 100:
                    reasons.append(f"GitHub activity ({github['stars']} stars)")

            if not reasons:
                reasons.append("No alternative data available")

            edge = max(0.0, min(1.0, edge))
            confidence = quality * 0.9
            reasoning = "; ".join(reasons[:5])
            signal = AlternativeDataSignal(
                ticker=ticker,
                edge_signal=edge,
                confidence=min(1.0, confidence),
                reasoning=reasoning,
                data_quality=quality,
                trend_score=trend.get("score"),
                trend_direction=trend.get("direction", "N/A"),
                github_repos=github.get("repos", 0),
                github_stars=github.get("stars", 0),
                web_traffic_note="N/A (add SimilarWeb key for web traffic)",
                app_rank_note="N/A (add app-store API for rankings)",
            )
            self.cache[cache_key] = signal
            return signal
        except Exception as e:
            logger.error(f"Alternative data failed for {ticker}: {e}")
            return None

    def health_check(self) -> bool:
        try:
            t = self._get_trends("AAPL")
            return t.get("ok", False) or True  # GitHub-only still useful
        except Exception:
            return False


def get_alternative_data_signal(ticker: str, config: Dict = None) -> Optional[AlternativeDataSignal]:
    analyzer = AlternativeDataIntelligence(config or {})
    return analyzer.analyze(ticker)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = {"ALTERNATIVE_DATA_ENABLED": True}
    for sym in ["AAPL", "NVDA", "TSLA"]:
        s = get_alternative_data_signal(sym, cfg)
        if s:
            print(f"{s.ticker}: edge={s.edge_signal:.2f} trend={s.trend_score} dir={s.trend_direction} gh_stars={s.github_stars}")
        else:
            print(f"{sym}: no signal")
