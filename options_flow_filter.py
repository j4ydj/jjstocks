#!/usr/bin/env python3
"""
Options flow filter — paid data path (Unusual Whales or similar).

When UNUSUAL_WHALES_API_KEY (or subscription token) is set, use options flow
as a filter on earnings signals: e.g. only take long when flow is bullish in that ticker.

API docs: https://docs.unusualwhales.com/ (subscription required).
Pricing: https://unusualwhales.com/pricing — Buffet's Buffet $32/mo (15min delay), Super Buffet $42/mo (live).
See PAID_DATA_AND_PATH.md for full paid-data path.
"""

import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Set to your Unusual Whales API key / token when you have a subscription
UW_API_KEY_ENV = "UNUSUAL_WHALES_API_KEY"
# Base URL for their API (check their docs for current endpoint)
UW_API_BASE = "https://api.unusualwhales.com"


def get_flow_summary(ticker: str, lookback_days: int = 5) -> Optional[Dict[str, Any]]:
    """
    Get options flow summary for ticker over last lookback_days.
    Returns None if no API key or request fails.
    Returns dict with e.g. bullish_ratio, net_premium_call_put, unusual_count.
    """
    api_key = os.environ.get(UW_API_KEY_ENV)
    if not api_key:
        return None
    try:
        import requests
        # Example: their API may have an endpoint like /flow or /options/activity
        # Replace with actual endpoint from Unusual Whales API docs
        url = f"{UW_API_BASE}/api/flow"
        params = {"symbol": ticker, "days": lookback_days}
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception as e:
        logger.debug("Unusual Whales flow %s: %s", ticker, e)
        return None


def is_bullish_flow(ticker: str, lookback_days: int = 5) -> Optional[bool]:
    """
    True = bullish flow in lookback period, False = bearish, None = unknown or no key.
    Implement logic based on Unusual Whales response (e.g. call vs put premium, sentiment flag).
    """
    summary = get_flow_summary(ticker, lookback_days)
    if summary is None:
        return None
    # Placeholder: adapt to actual API response shape
    # e.g. if they return "sentiment": "bullish" or "call_premium" > "put_premium"
    bullish = summary.get("bullish") or summary.get("sentiment") == "bullish"
    if isinstance(bullish, bool):
        return bullish
    return None


def filter_signals_by_flow(signals: list, lookback_days: int = 5) -> list:
    """
    Keep only signals where options flow is bullish (or neutral if we can't get flow).
    signals: list of dicts with "ticker" key.
    """
    if not os.environ.get(UW_API_KEY_ENV):
        return signals
    out = []
    for s in signals:
        ticker = s.get("ticker")
        if not ticker:
            out.append(s)
            continue
        bull = is_bullish_flow(ticker, lookback_days)
        if bull is None:
            out.append(s)  # no data -> keep
        elif bull:
            out.append(s)
        # else skip (bearish flow)
    return out
