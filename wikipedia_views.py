#!/usr/bin/env python3
"""
Wikipedia Pageview Momentum — Path Less Travelled
=================================================
Free edge: rising Wikipedia pageviews = rising attention. Use as filter or ranking.

Uses Wikimedia Pageviews API only. Requires a descriptive User-Agent.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

WIKI_USER_AGENT = "TradingBot/1.0 (Educational; contact@example.com)"
PAGEVIEWS_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
WIKI_API = "https://en.wikipedia.org/w/api.php"


def _headers(config: Optional[Dict] = None) -> Dict[str, str]:
    ua = (config or {}).get("WIKI_USER_AGENT", WIKI_USER_AGENT)
    return {"User-Agent": ua}


# Small map for common tickers → Wikipedia article title (URL form: spaces as underscores)
TICKER_TO_TITLE: Dict[str, str] = {
    "AAPL": "Apple_Inc.",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet_Inc.",
    "AMZN": "Amazon_(company)",
    "TSLA": "Tesla,_Inc.",
    "META": "Meta_Platforms",
    "NVDA": "Nvidia",
    "JPM": "JPMorgan_Chase",
    "V": "Visa_Inc.",
    "UNH": "UnitedHealth_Group",
    "COIN": "Coinbase",
    "RBLX": "Roblox",
    "CRWD": "CrowdStrike",
    "DDOG": "Datadog",
    "NET": "Cloudflare",
    "MDB": "MongoDB",
    "HUBS": "HubSpot",
    "CELH": "Celsius_Holdings",
    "RIVN": "Rivian",
    "LCID": "Lucid_Group",
    "PLUG": "Plug_Power",
    "GME": "GameStop",
    "AMC": "AMC_Theatres",
}


def _ticker_to_article_title(ticker: str, config: Optional[Dict] = None) -> Optional[str]:
    """Resolve ticker to Wikipedia article title (URL-safe)."""
    ticker = (ticker or "").upper().strip()
    if ticker in TICKER_TO_TITLE:
        return TICKER_TO_TITLE[ticker]
    # Fallback: search Wikipedia for "{ticker} (company)" or "{ticker} stock"
    try:
        r = requests.get(
            WIKI_API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{ticker} company stock",
                "format": "json",
                "srlimit": 3,
            },
            headers=_headers(config),
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        hits = data.get("query", {}).get("search") or []
        for h in hits:
            title = h.get("title", "")
            if title and not title.startswith("List of"):
                return title.replace(" ", "_")
        return None
    except Exception as e:
        logger.debug("Wikipedia search for %s: %s", ticker, e)
        return None


def get_pageviews(
    ticker: str,
    days: int = 30,
    config: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    Get daily pageview counts for the company's Wikipedia page.
    Returns {"daily": [(date_str, views), ...], "total": int, "title": str} or None.
    """
    title = _ticker_to_article_title(ticker, config)
    if not title:
        return None

    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y%m%d")
    end_str = end.strftime("%Y%m%d")
    url = f"{PAGEVIEWS_BASE}/en.wikipedia.org/all-access/all-agents/{quote(title)}/daily/{start_str}/{end_str}"

    try:
        r = requests.get(url, headers=_headers(config), timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        items = data.get("items") or []
        daily = [(item["timestamp"][:8], item.get("views", 0)) for item in items]
        total = sum(v for _, v in daily)
        return {"daily": daily, "total": total, "title": title}
    except Exception as e:
        logger.debug("Pageviews for %s: %s", ticker, e)
        return None


def trend(
    ticker: str,
    window_days: int = 14,
    config: Optional[Dict] = None,
) -> str:
    """
    Compare first half vs second half of window. Returns "up", "down", or "flat".
    """
    pw = get_pageviews(ticker, days=window_days, config=config)
    if not pw or not pw["daily"]:
        return "flat"

    daily = pw["daily"]
    n = len(daily)
    if n < 4:
        return "flat"
    mid = n // 2
    first_half = sum(v for _, v in daily[:mid])
    second_half = sum(v for _, v in daily[mid:])
    if second_half > first_half * 1.1:
        return "up"
    if second_half < first_half * 0.9:
        return "down"
    return "flat"


def trend_score(ticker: str, window_days: int = 14, config: Optional[Dict] = None) -> float:
    """
    Returns -1 to 1: negative = declining views, positive = rising views.
    Use for ranking (prefer rising attention).
    """
    pw = get_pageviews(ticker, days=window_days, config=config)
    if not pw or not pw["daily"]:
        return 0.0

    daily = pw["daily"]
    n = len(daily)
    if n < 4:
        return 0.0
    mid = n // 2
    first_half = sum(v for _, v in daily[:mid])
    second_half = sum(v for _, v in daily[mid:])
    if first_half <= 0:
        return 0.0
    # ratio > 1 => up, < 1 => down
    ratio = second_half / first_half
    if ratio >= 1.5:
        return 1.0
    if ratio <= 0.67:
        return -1.0
    return (ratio - 1.0) * 2.0  # roughly -0.66 to 0.66 for 0.67–1.5


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = {}
    for sym in ["AAPL", "TSLA", "GME", "CRWD"]:
        t = trend(sym, 14, cfg)
        s = trend_score(sym, 14, cfg)
        print(f"{sym}: trend={t} score={s:.2f}")
