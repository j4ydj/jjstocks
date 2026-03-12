#!/usr/bin/env python3
"""
PREDICTION MARKET + EARNINGS EDGE
=================================
Hypothesis: Fade prediction market pessimism when earnings surprise beats.
When Polymarket/Kalshi shows <40% odds of a beat but company beats EPS,
the price pop is larger due to surprise against expectations.

Ready to implement - uses existing free data sources.
"""
import logging
from typing import Dict, List, Optional
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from prediction_markets import fetch_tradeable_markets, get_earnings_beat_odds
from run_winning_strategy import get_earnings_surprise

class PMEarningsEdge:
    """
    Combines prediction market odds with earnings surprises.
    """
    
    def __init__(self, odds_threshold: float = 0.40):
        """
        Args:
            odds_threshold: Only consider when PM odds < this (pessimistic)
        """
        self.odds_threshold = odds_threshold
    
    def check_opportunity(self, ticker: str) -> Optional[Dict]:
        """
        Check if there's a PM earnings edge opportunity.
        
        Returns dict if opportunity exists, None otherwise.
        """
        # Get current prediction market odds
        odds = get_earnings_beat_odds(ticker)
        
        # Get recent earnings
        surprise_data = get_earnings_surprise(ticker)
        
        if not surprise_data:
            return None
        
        surprise_pct = surprise_data.get("surprise_pct", 0)
        
        # Check if PM was pessimistic but we beat
        if odds and odds < self.odds_threshold and surprise_pct > 10:
            return {
                "ticker": ticker,
                "pm_odds": odds,
                "surprise_pct": surprise_pct,
                "signal": "STRONG_BUY",  # PM wrong, reality beat
                "edge": f"PM {odds:.0%} pessimistic but beat by {surprise_pct:.1f}%",
                "confidence": "HIGH" if surprise_pct > 20 else "MEDIUM"
            }
        
        # Check if PM was too optimistic and we barely beat
        if odds and odds > 0.70 and surprise_pct < 5:
            return {
                "ticker": ticker,
                "pm_odds": odds,
                "surprise_pct": surprise_pct,
                "signal": "AVOID",  # Already priced in
                "edge": "High expectations, weak beat - likely sell-off",
                "confidence": "MEDIUM"
            }
        
        return None
    
    def scan_universe(self, tickers: List[str]) -> List[Dict]:
        """Scan universe for PM + earnings edge opportunities."""
        opportunities = []
        
        for ticker in tickers:
            opp = self.check_opportunity(ticker)
            if opp and opp.get("signal") == "STRONG_BUY":
                opportunities.append(opp)
        
        return opportunities

def main():
    """Run PM + Earnings edge scanner."""
    logger.info("=" * 70)
    logger.info("  PREDICTION MARKET + EARNINGS EDGE SCANNER")
    logger.info("=" * 70)
    
    # Test tickers with active prediction markets
    test_tickers = ["AAPL", "TSLA", "NVDA", "META", "AMZN", "GOOGL"]
    
    edge = PMEarningsEdge(odds_threshold=0.40)
    opportunities = edge.scan_universe(test_tickers)
    
    if opportunities:
        logger.info(f"\n🎯 Found {len(opportunities)} opportunities:\n")
        for opp in opportunities:
            logger.info(f"  {opp['ticker']}")
            logger.info(f"    PM Odds: {opp['pm_odds']:.0%}")
            logger.info(f"    Surprise: {opp['surprise_pct']:+.1f}%")
            logger.info(f"    Edge: {opp['edge']}")
            logger.info(f"    Confidence: {opp['confidence']}\n")
    else:
        logger.info("\n  No PM + Earnings edges found currently.")
        logger.info("  (Requires active prediction markets with earnings events)")
    
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
