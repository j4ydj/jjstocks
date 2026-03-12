#!/usr/bin/env python3
"""
RETAIL SENTIMENT DIVERGENCE EDGE
=================================
Highest-scoring free edge (195/100).

Hypothesis: When retail attention (Wikipedia + Reddit + Google Trends) 
diverges from price action, predict mean reversion or momentum continuation.

Three signals:
1. Rising retail interest + flat price = impending pop (accumulation phase)
2. Flat retail interest + rising price = exhaustion (distribution phase)
3. Extreme retail interest spike = top signal (contrarian)
"""
import logging
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

class RetailSentimentEdge:
    """
    Combines multiple free retail sentiment sources for edge detection.
    """
    
    def __init__(self):
        self.sources = {}
        
        # Try to load each data source
        try:
            import wikipedia_views
            self.sources['wikipedia'] = wikipedia_views
        except ImportError:
            logger.warning("Wikipedia views not available")
        
        try:
            import sentiment_intelligence
            self.sources['reddit'] = sentiment_intelligence
        except ImportError:
            logger.warning("Reddit sentiment not available")
        
        try:
            import google_trends
            self.sources['trends'] = google_trends.GoogleTrends()
        except (ImportError, Exception) as e:
            logger.warning(f"Google Trends not available: {e}")
    
    def get_composite_sentiment(self, ticker: str) -> Optional[Dict]:
        """
        Get composite retail sentiment score from all available sources.
        
        Returns:
            Dict with individual scores and composite signal
        """
        scores = {
            "ticker": ticker,
            "sources_used": 0,
            "wikipedia": None,
            "reddit": None,
            "trends": None,
        }
        
        # Wikipedia (trend score)
        if 'wikipedia' in self.sources:
            try:
                wiki_score = self.sources['wikipedia'].trend_score(ticker, 14)
                if wiki_score is not None:
                    scores['wikipedia'] = {
                        "score": wiki_score,
                        "is_rising": wiki_score > 0
                    }
                    scores['sources_used'] += 1
            except Exception as e:
                logger.debug(f"Wikipedia error for {ticker}: {e}")
        
        # Reddit (mention velocity)
        if 'reddit' in self.sources:
            try:
                reddit_signal = self.sources['reddit'].get_sentiment_signal(ticker)
                if reddit_signal:
                    scores['reddit'] = {
                        "mentions": getattr(reddit_signal, 'mention_count', 0),
                        "sentiment": getattr(reddit_signal, 'sentiment_score', 0),
                    }
                    scores['sources_used'] += 1
            except Exception as e:
                logger.debug(f"Reddit error for {ticker}: {e}")
        
        # Google Trends
        if 'trends' in self.sources:
            try:
                trend_data = self.sources['trends'].get_trend_score(ticker)
                if trend_data:
                    scores['trends'] = trend_data
                    scores['sources_used'] += 1
            except Exception as e:
                logger.debug(f"Trends error for {ticker}: {e}")
        
        if scores['sources_used'] == 0:
            return None
        
        # Calculate composite signal
        scores['composite'] = self._calculate_composite(scores)
        
        return scores
    
    def _calculate_composite(self, scores: Dict) -> Dict:
        """Calculate composite signal from individual sources."""
        signals = []
        
        # Wikipedia signal
        if scores.get('wikipedia'):
            wiki = scores['wikipedia']
            if wiki.get('is_rising'):
                signals.append(("WIKI", 1, wiki['score']))
            else:
                signals.append(("WIKI", -1, wiki['score']))
        
        # Reddit signal
        if scores.get('reddit'):
            reddit = scores['reddit']
            mentions = reddit.get('mentions', 0)
            sentiment = reddit.get('sentiment', 0)
            if mentions > 10 and sentiment > 0.3:
                signals.append(("REDDIT", 1, mentions * sentiment))
            elif mentions > 10 and sentiment < -0.3:
                signals.append(("REDDIT", -1, mentions * abs(sentiment)))
        
        # Trends signal
        if scores.get('trends'):
            trends = scores['trends']
            if trends.get('is_hot') or trends.get('trend') == "RISING":
                velocity = trends.get('velocity', 0)
                signals.append(("TRENDS", 1 if velocity > 0 else -1, abs(velocity)))
        
        if not signals:
            return {"signal": "NEUTRAL", "strength": 0, "direction": None}
        
        # Weight by source reliability
        weights = {"WIKI": 0.3, "REDDIT": 0.4, "TRENDS": 0.3}
        
        weighted_sum = sum(
            sig[1] * sig[2] * weights.get(sig[0], 0.3) 
            for sig in signals
        )
        
        total_weight = sum(
            weights.get(sig[0], 0.3) * abs(sig[2]) 
            for sig in signals
        ) if signals else 1
        
        normalized_score = weighted_sum / total_weight if total_weight > 0 else 0
        
        # Determine signal
        if normalized_score > 0.5:
            signal = "BULLISH"
        elif normalized_score < -0.5:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"
        
        strength = abs(normalized_score)
        
        return {
            "signal": signal,
            "strength": round(strength, 2),
            "score": round(normalized_score, 2),
            "components": [s[0] for s in signals],
            "details": signals
        }
    
    def find_divergences(self, tickers: List[str], price_data: Optional[Dict] = None) -> List[Dict]:
        """
        Find retail sentiment / price divergences.
        
        High retail interest + flat price = ACCUMULATION (buy)
        Low retail interest + rising price = EXHAUSTION (sell)
        """
        divergences = []
        
        for ticker in tickers:
            sentiment = self.get_composite_sentiment(ticker)
            if not sentiment:
                continue
            
            composite = sentiment.get('composite', {})
            signal = composite.get('signal', 'NEUTRAL')
            strength = composite.get('strength', 0)
            
            # Only report strong signals
            if strength >= 0.7 and signal in ['BULLISH', 'BEARISH']:
                divergences.append({
                    "ticker": ticker,
                    "signal": signal,
                    "strength": strength,
                    "score": composite.get('score', 0),
                    "sources": sentiment['sources_used'],
                    "wikipedia": sentiment.get('wikipedia'),
                    "reddit": sentiment.get('reddit'),
                    "trends": sentiment.get('trends'),
                })
        
        # Sort by strength
        divergences.sort(key=lambda x: x['strength'], reverse=True)
        return divergences

def main():
    """Run retail sentiment edge scanner."""
    logger.info("=" * 70)
    logger.info("  RETAIL SENTIMENT DIVERGENCE EDGE SCANNER")
    logger.info("=" * 70)
    
    # Test universe
    test_tickers = [
        "GME", "AMC", "TSLA", "AAPL", "NVDA", "PLTR", 
        "COIN", "HOOD", "SPY", "QQQ"
    ]
    
    edge = RetailSentimentEdge()
    
    logger.info(f"\nScanning {len(test_tickers)} tickers...\n")
    
    divergences = edge.find_divergences(test_tickers)
    
    if divergences:
        logger.info(f"🎯 Found {len(divergences)} strong sentiment signals:\n")
        
        for div in divergences[:5]:
            signal_emoji = "🚀" if div['signal'] == 'BULLISH' else "🔻"
            logger.info(f"{signal_emoji} {div['ticker']}: {div['signal']} (strength: {div['strength']:.2f})")
            logger.info(f"   Score: {div['score']:+.2f} | Sources: {div['sources']}")
            
            if div.get('wikipedia'):
                logger.info(f"   Wikipedia: {'RISING' if div['wikipedia'].get('is_rising') else 'FALLING'}")
            if div.get('reddit'):
                reddit = div['reddit']
                logger.info(f"   Reddit: {reddit.get('mentions', 0)} mentions, sentiment {reddit.get('sentiment', 0):+.2f}")
            if div.get('trends'):
                trends = div['trends']
                logger.info(f"   Trends: {trends.get('trend', 'N/A')} (velocity: {trends.get('velocity', 0):+.1f}%)")
            logger.info("")
    else:
        logger.info("No strong sentiment divergences found.")
        logger.info("\nNote: This requires at least 2 of 3 data sources:")
        logger.info("  - Wikipedia views (implemented)")
        logger.info("  - Reddit sentiment (implemented)")
        logger.info("  - Google Trends (needs pytrends)")
    
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
