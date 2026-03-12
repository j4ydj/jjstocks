#!/usr/bin/env python3
"""
Fast Scan — Short-term, high-volume watchlist
==============================================
Combines:
  - Volume anomaly (accumulation / spike) from volume_anomaly.py
  - Optional: Polymarket tradeable markets (Fed, macro, any stock-related)
  - Optional: sentiment (existing sentiment_intelligence) for top names

Use for SHORT-TERM edges: names with volume spike + (optional) prediction market or buzz.
Long-term strategy remains run_winning_strategy.py (earnings 40d hold).

Usage:
  ./venv/bin/python fast_scan.py                    # volume-only
  ./venv/bin/python fast_scan.py --polymarket        # + Polymarket tradeable list
  ./venv/bin/python fast_scan.py --polymarket --sentiment  # + sentiment on top N
"""

import logging
import sys
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEFAULT_UNIVERSE = [
    "CRWD", "DDOG", "NET", "ZS", "MDB", "HUBS", "SOFI", "HOOD", "AFRM", "UPST",
    "CELH", "CAVA", "ELF", "ONON", "CROX", "RKLB", "RIVN", "LCID", "PLUG", "GME",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "COIN", "RBLX",
]


def run_volume_scan(tickers: List[str], config: dict = None) -> list:
    """Return list of volume signals (accumulation or spike)."""
    try:
        from volume_anomaly import scan_volume_universe
        return scan_volume_universe(tickers, config)
    except ImportError:
        logger.warning("volume_anomaly not available")
        return []


def run_polymarket(config: dict = None) -> list:
    """Return list of tradeable prediction markets (relevant keywords)."""
    try:
        from prediction_markets import fetch_tradeable_markets
        return fetch_tradeable_markets(active_only=True, limit=50, filter_relevant=True)
    except ImportError:
        logger.warning("prediction_markets not available")
        return []


def run_sentiment(ticker: str, config: dict = None) -> Optional[float]:
    """Return sentiment score for ticker if available."""
    try:
        from sentiment_intelligence import get_sentiment_signal
        s = get_sentiment_signal(ticker, config)
        return s.sentiment_score if s else None
    except ImportError:
        return None


def main():
    import argparse
    p = argparse.ArgumentParser(description="Fast scan: volume + optional Polymarket + optional sentiment")
    p.add_argument("--polymarket", action="store_true", help="Fetch Polymarket tradeable markets")
    p.add_argument("--sentiment", action="store_true", help="Get sentiment for top volume names (slow)")
    p.add_argument("--top", type=int, default=15, help="Show top N volume names (default 15)")
    args = p.parse_args()

    tickers = DEFAULT_UNIVERSE
    config = {}

    logger.info("=== FAST SCAN (short-term edges) ===\n")

    # 1. Volume
    signals = run_volume_scan(tickers, config)
    if not signals:
        logger.info("No volume signals. Try a larger universe or check volume_anomaly.")
    else:
        signals.sort(key=lambda s: (s.accumulation_score, s.volume_multiple), reverse=True)
        top = signals[: args.top]
        logger.info("Volume anomalies (top %d):", len(top))
        for s in top:
            logger.info("  %s  %s  vol=%.1fx  acc=%.0f  5d=%+.1f%%",
                        s.ticker, s.signal, s.volume_multiple, s.accumulation_score, s.price_change_5d)
        if args.sentiment and top:
            logger.info("")
            for s in top[:5]:
                score = run_sentiment(s.ticker, config)
                if score is not None:
                    logger.info("  %s sentiment: %+.2f", s.ticker, score)

    if args.polymarket:
        logger.info("")
        markets = run_polymarket(config)
        if markets:
            logger.info("Polymarket (tradeable, relevant): %d markets", len(markets))
            for m in markets[:10]:
                logger.info("  %.0f%% Yes  %s", m["yes_prob"] * 100, m["title"][:55])
        else:
            logger.info("Polymarket: no relevant active markets or API unavailable.")

    logger.info("")
    logger.info("Use these as SHORT-TERM watchlist or filter for earnings strategy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
