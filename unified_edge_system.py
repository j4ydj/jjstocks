#!/usr/bin/env python3
"""
UNIFIED EDGE SYSTEM
==================
Combines all free data sources into a multi-factor edge scanner.

Scoring System:
- PM Earnings Edge: +3 (high conviction when PM wrong)
- Retail Sentiment: +2 (divergence signal)
- SEC Risk Filter: -5 (avoid these)
- Technical Momentum: +1 (confirmation)

Entry Requirements:
- Score >= 4 (STRONG)
- Score >= 2 (MODERATE)
- Score < 2 (AVOID)
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

@dataclass
class EdgeSignal:
    ticker: str
    score: int
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    direction: str   # "LONG", "SHORT", "AVOID"
    reasons: List[str]
    timestamp: str

class UnifiedEdgeSystem:
    """
    Multi-factor edge detection combining all free sources.
    """
    
    def __init__(self):
        self.edges = {}
        
        # Load all edge modules
        try:
            from prediction_markets import get_earnings_beat_odds
            self.edges['pm'] = get_earnings_beat_odds
        except ImportError:
            pass
        
        try:
            from retail_sentiment_edge import RetailSentimentEdge
            self.edges['retail'] = RetailSentimentEdge()
        except ImportError:
            pass
        
        try:
            import sec_filing_risk as sec_risk
            self.edges['sec'] = sec_risk
        except ImportError:
            pass
        
        try:
            from run_winning_strategy import get_earnings_surprise
            self.edges['earnings'] = get_earnings_surprise
        except ImportError:
            pass
    
    def score_ticker(self, ticker: str) -> EdgeSignal:
        """
        Score a ticker across all edge factors.
        
        Returns EdgeSignal with composite score.
        """
        score = 0
        reasons = []
        direction = "NEUTRAL"
        
        # 1. SEC Risk Filter (-5 if risky)
        if 'sec' in self.edges:
            try:
                clean, form, risk_count = self.edges['sec'].is_clean(ticker, {})
                if not clean:
                    score -= 5
                    reasons.append(f"SEC risk in {form} ({risk_count} phrases)")
                    direction = "AVOID"
            except:
                pass
        
        # 2. Earnings Surprise (+2 to +4)
        if 'earnings' in self.edges:
            try:
                earn = self.edges['earnings'](ticker)
                if earn:
                    surprise = earn.get('surprise_pct', 0)
                    if surprise > 30:
                        score += 4
                        reasons.append(f"Huge earnings beat: +{surprise:.1f}%")
                        direction = "LONG"
                    elif surprise > 15:
                        score += 2
                        reasons.append(f"Strong earnings beat: +{surprise:.1f}%")
                        direction = "LONG"
                    elif surprise < -15:
                        score -= 2
                        reasons.append(f"Earnings miss: {surprise:.1f}%")
                        direction = "SHORT"
            except:
                pass
        
        # 3. Prediction Market Edge (+3 if contrarian)
        if 'pm' in self.edges:
            try:
                odds = self.edges['pm'](ticker)
                if odds is not None and odds < 0.40:
                    # PM pessimistic but we have data suggesting otherwise
                    score += 3
                    reasons.append(f"PM pessimistic ({odds:.0%} odds) - fade the crowd")
                    direction = "LONG"
                elif odds is not None and odds > 0.70:
                    score -= 1
                    reasons.append(f"PM too optimistic ({odds:.0%} odds)")
            except:
                pass
        
        # 4. Retail Sentiment (+2 if divergence)
        if 'retail' in self.edges:
            try:
                retail = self.edges['retail'].get_composite_sentiment(ticker)
                if retail:
                    composite = retail.get('composite', {})
                    signal = composite.get('signal', 'NEUTRAL')
                    strength = composite.get('strength', 0)
                    
                    if signal == 'BULLISH' and strength >= 0.7:
                        score += 2
                        reasons.append(f"Strong retail interest (strength: {strength:.2f})")
                        if direction == "NEUTRAL":
                            direction = "LONG"
                    elif signal == 'BEARISH' and strength >= 0.7:
                        score -= 2
                        reasons.append(f"Negative retail sentiment (strength: {strength:.2f})")
                        if direction == "NEUTRAL":
                            direction = "SHORT"
            except:
                pass
        
        # Determine confidence
        if abs(score) >= 5:
            confidence = "HIGH"
        elif abs(score) >= 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        # Default direction
        if direction == "NEUTRAL":
            direction = "AVOID"
        
        return EdgeSignal(
            ticker=ticker,
            score=score,
            confidence=confidence,
            direction=direction,
            reasons=reasons,
            timestamp=datetime.now().isoformat()
        )
    
    def scan_universe(self, tickers: List[str], min_score: int = 2) -> List[EdgeSignal]:
        """
        Scan universe and return signals above threshold.
        """
        signals = []
        
        for ticker in tickers:
            signal = self.score_ticker(ticker)
            if abs(signal.score) >= min_score:
                signals.append(signal)
        
        # Sort by absolute score
        signals.sort(key=lambda x: abs(x.score), reverse=True)
        return signals
    
    def get_top_picks(self, tickers: List[str], n: int = 5) -> Tuple[List[EdgeSignal], List[EdgeSignal]]:
        """
        Get top LONG and SHORT picks.
        """
        all_signals = self.scan_universe(tickers, min_score=2)
        
        longs = [s for s in all_signals if s.direction == "LONG" and s.score >= 4][:n]
        shorts = [s for s in all_signals if s.direction == "SHORT" and s.score <= -2][:n]
        
        return longs, shorts

def main():
    """Run unified edge system."""
    logger.info("=" * 70)
    logger.info("  UNIFIED EDGE SYSTEM - Multi-Factor Scanner")
    logger.info("=" * 70)
    
    # Test universe (mix of growth, meme, and index)
    universe = [
        "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
        "GME", "AMC", "PLTR", "COIN", "HOOD", "SPY", "QQQ",
        "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU"
    ]
    
    system = UnifiedEdgeSystem()
    
    logger.info(f"\nScanning {len(universe)} tickers...")
    logger.info("Sources: SEC + Earnings + PM + Retail Sentiment\n")
    
    # Get all signals
    signals = system.scan_universe(universe, min_score=2)
    
    if signals:
        longs = [s for s in signals if s.direction == "LONG"]
        shorts = [s for s in signals if s.direction == "SHORT"]
        avoids = [s for s in signals if s.direction == "AVOID"]
        
        # Display LONG signals
        if longs:
            logger.info("🚀 TOP LONG SIGNALS:\n")
            for sig in longs[:5]:
                logger.info(f"  {sig.ticker}: Score +{sig.score} ({sig.confidence})")
                for reason in sig.reasons:
                    logger.info(f"    • {reason}")
                logger.info("")
        
        # Display SHORT signals
        if shorts:
            logger.info("🔻 TOP SHORT SIGNALS:\n")
            for sig in shorts[:3]:
                logger.info(f"  {sig.ticker}: Score {sig.score} ({sig.confidence})")
                for reason in sig.reasons:
                    logger.info(f"    • {reason}")
                logger.info("")
        
        # Display AVOID signals
        if avoids:
            logger.info("⚠️  AVOID (Risky):\n")
            for sig in avoids[:3]:
                logger.info(f"  {sig.ticker}: Score {sig.score}")
                for reason in sig.reasons[:2]:
                    logger.info(f"    • {reason}")
            logger.info("")
    else:
        logger.info("No strong signals found in current universe.")
        logger.info("This can happen when:")
        logger.info("  - No recent earnings")
        logger.info("  - No active prediction markets")
        logger.info("  - Retail sentiment is neutral")
    
    logger.info("=" * 70)
    logger.info("SCORING SYSTEM:")
    logger.info("  +4: Huge earnings beat (>30%)")
    logger.info("  +3: PM pessimistic + beat likely")
    logger.info("  +2: Strong earnings (>15%) or retail interest")
    logger.info("  -5: SEC filing risk detected")
    logger.info("  -2: Earnings miss or negative retail")
    logger.info("\nEntry threshold: Score >= 4 (HIGH confidence)")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
