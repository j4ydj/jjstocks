#!/usr/bin/env python3
"""
Trader Attention — StockTwits-based signal
=========================================
Uses StockTwits symbol stream (trader chatter) instead of Wikipedia.
Attention from traders, not general web traffic.
"""
import logging
from typing import Optional, Dict

import requests

logger = logging.getLogger(__name__)

STOCKTWITS_SYMBOL_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
REQUEST_TIMEOUT = 8


def trend_score(ticker: str, _window_days: int = None, config: Optional[Dict] = None) -> Optional[float]:
    """
    Returns -1 to 1 from StockTwits: negative = bearish sentiment, positive = bullish.
    Based on recent message sentiment (Bullish/Bearish) in the symbol stream.
    """
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return None
    url = STOCKTWITS_SYMBOL_URL.format(symbol=ticker)
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.debug("StockTwits fetch %s: %s", ticker, e)
        return None

    messages = data.get("messages") or []
    if not messages:
        return None

    bullish = bearish = 0
    for m in messages:
        sent = (m.get("entities") or {}).get("sentiment") or m.get("sentiment") or {}
        s = (sent.get("basic") or str(sent)).upper()
        if "BULLISH" in s or s == "BULLISH":
            bullish += 1
        elif "BEARISH" in s or s == "BEARISH":
            bearish += 1

    total = bullish + bearish
    if total == 0:
        return None
    # Score: (bullish - bearish) / total, scaled to roughly -1..1
    raw = (bullish - bearish) / total
    return max(-1.0, min(1.0, raw))
