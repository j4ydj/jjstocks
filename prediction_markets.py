#!/usr/bin/env python3
"""
Prediction Markets — Fast Edge (Free)
======================================
Polymarket (and optionally others) give implied probabilities for events.
Use as SHORT-TERM filter: only take earnings longs when "beat" odds are high,
or trade the underlying before resolution when we disagree with the crowd.

APIs: Polymarket Gamma API (no auth). See FAST_EDGES.md.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
USER_AGENT = "TradingBot/1.0 (Educational; contact@example.com)"

# Keywords to keep events that might be tradeable (stocks, earnings, macro)
RELEVANT_KEYWORDS = re.compile(
    r"earnings|beat|revenue|eps|stock|share price|trump|biden|fed|rate cut|rate hike|"
    r"cpi|inflation|jobs report|tesla|apple|nvda|amazon|meta|google|microsoft",
    re.I,
)


def _get_events(
    active: bool = True,
    closed: bool = False,
    limit: int = 50,
    order: str = "volume24hr",
    ascending: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch events from Polymarket Gamma API. No auth required."""
    params = {
        "active": str(active).lower(),
        "closed": str(closed).lower(),
        "limit": limit,
        "order": order,
        "ascending": str(ascending).lower(),
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    try:
        r = requests.get(
            f"{GAMMA_BASE}/events",
            params=params,
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("Polymarket Gamma API failed: %s", e)
        return []


def _parse_yes_prob(market: Dict[str, Any]) -> Optional[float]:
    """From a market's outcomePrices (JSON string), return Yes probability."""
    raw = market.get("outcomePrices")
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            prices = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        prices = raw
    if not prices or len(prices) < 2:
        return None
    try:
        return float(prices[0])
    except (TypeError, ValueError):
        return None


def _event_relevant(event: Dict[str, Any]) -> bool:
    """True if event title/slug/description suggests tradeable (stocks, macro)."""
    title = (event.get("title") or "").lower()
    slug = (event.get("slug") or "").lower()
    desc = (event.get("description") or "").lower()
    text = " ".join([title, slug, desc])
    return bool(RELEVANT_KEYWORDS.search(text))


def fetch_tradeable_markets(
    active_only: bool = True,
    limit: int = 100,
    filter_relevant: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch Polymarket events and return tradeable markets with implied Yes probability.
    If filter_relevant=True, only return events matching earnings/stock/fed/keywords.
    Returns list of {
        "event_id", "title", "slug", "yes_prob", "volume", "end_date", "category",
        "question"
    }.
    """
    events = _get_events(active=active_only, closed=False, limit=limit, order="volume24hr", ascending=False)
    out = []
    for ev in events:
        if filter_relevant and not _event_relevant(ev):
            continue
        markets = ev.get("markets") or []
        if not markets:
            continue
        m = markets[0]
        yes_prob = _parse_yes_prob(m)
        if yes_prob is None:
            continue
        out.append({
            "event_id": ev.get("id"),
            "title": ev.get("title", ""),
            "slug": ev.get("slug", ""),
            "yes_prob": round(yes_prob, 4),
            "volume": float(ev.get("volume") or m.get("volume") or 0),
            "end_date": ev.get("endDate") or m.get("endDate"),
            "category": ev.get("category", ""),
            "question": m.get("question", ev.get("title", "")),
        })
    return out


def get_earnings_beat_odds(ticker: str) -> Optional[float]:
    """
    If Polymarket has an active market like 'Will X beat earnings?', return implied Yes probability.
    Otherwise None. Ticker should be upper case (e.g. AAPL).
    """
    events = _get_events(active=True, closed=False, limit=100, order="volume24hr", ascending=False)
    ticker_lower = ticker.lower()
    for ev in events:
        title = (ev.get("title") or "").lower()
        slug = (ev.get("slug") or "").lower()
        if ticker_lower not in title and ticker_lower not in slug:
            continue
        if "earnings" not in title and "beat" not in title and "revenue" not in title:
            continue
        markets = ev.get("markets") or []
        if not markets:
            continue
        yes_prob = _parse_yes_prob(markets[0])
        if yes_prob is not None:
            return round(yes_prob, 4)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    markets = fetch_tradeable_markets(active_only=True, limit=80, filter_relevant=True)
    logger.info("Tradeable prediction markets (sample): %d", len(markets))
    for m in markets[:15]:
        logger.info("  %.0f%% Yes | %s | vol=%s", m["yes_prob"] * 100, m["title"][:60], m["volume"])
    for t in ["AAPL", "TSLA", "NVDA"]:
        odds = get_earnings_beat_odds(t)
        logger.info("  %s earnings beat odds: %s", t, f"{odds*100:.0f}%" if odds is not None else "no market")
