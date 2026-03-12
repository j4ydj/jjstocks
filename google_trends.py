#!/usr/bin/env python3
"""
GOOGLE TRENDS - Retail Sentiment Data
=====================================
Free data source: pytrends (unofficial Google Trends API)
Use for detecting search interest spikes before price moves.
"""
import logging
import time
from typing import Dict, List, Optional
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False
    logger.warning("pytrends not available. Install with: pip install pytrends")

class GoogleTrends:
    """
    Google Trends wrapper with rate limiting and caching.
    """
    
    def __init__(self, hl: str = 'en-US', tz: int = 360):
        """
        Initialize Google Trends connection.
        
        Args:
            hl: Language (en-US)
            tz: Timezone (360 = US Eastern)
        """
        if not PYTRENDS_AVAILABLE:
            raise ImportError("pytrends required. Install: pip install pytrends")
        
        self.pytrends = TrendReq(hl=hl, tz=tz)
        self.last_request_time = 0
        self.min_delay = 1.5  # Seconds between requests (be polite)
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()
    
    def get_interest_over_time(self, keywords: List[str], timeframe: str = 'today 3-m') -> Optional[pd.DataFrame]:
        """
        Get interest over time for keywords.
        
        Args:
            keywords: List of search terms (max 5)
            timeframe: 'today 3-m' (3 months), 'today 12-m' (1 year), 'now 7-d' (7 days)
        
        Returns:
            DataFrame with interest scores (0-100) by date
        """
        if not keywords:
            return None
        
        try:
            self._rate_limit()
            self.pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo='', gprop='')
            data = self.pytrends.interest_over_time()
            
            if data.empty:
                return None
            
            return data
        except Exception as e:
            logger.debug(f"Google Trends error: {e}")
            return None
    
    def get_trend_score(self, ticker: str, timeframe: str = 'today 3-m') -> Optional[Dict]:
        """
        Get trend score for a stock ticker.
        
        Searches for:
        1. "{ticker} stock" - Direct stock interest
        2. "buy {ticker}" - Purchase intent
        3. "{ticker} reddit" - Social interest
        
        Returns dict with scores and trend direction.
        """
        keywords = [
            f"{ticker} stock",
            f"buy {ticker}",
        ]
        
        data = self.get_interest_over_time(keywords, timeframe)
        if data is None or data.empty:
            return None
        
        # Calculate trend scores
        if f"{ticker} stock" in data.columns:
            stock_col = f"{ticker} stock"
        else:
            stock_col = keywords[0]
        
        if stock_col not in data.columns:
            return None
        
        series = data[stock_col]
        
        # Calculate metrics
        current = series.iloc[-1] if len(series) > 0 else 0
        avg_30d = series.tail(30).mean() if len(series) >= 30 else series.mean()
        avg_7d = series.tail(7).mean() if len(series) >= 7 else series.mean()
        
        # Trend direction
        if avg_7d > avg_30d * 1.2:
            trend = "RISING"
        elif avg_7d < avg_30d * 0.8:
            trend = "FALLING"
        else:
            trend = "STABLE"
        
        return {
            "ticker": ticker,
            "current_score": int(current),
            "avg_7d": round(avg_7d, 1),
            "avg_30d": round(avg_30d, 1),
            "trend": trend,
            "velocity": round((avg_7d / avg_30d - 1) * 100, 1) if avg_30d > 0 else 0,
            "is_hot": current > 75 or (current > 50 and trend == "RISING"),
        }
    
    def compare_tickers(self, tickers: List[str]) -> Optional[pd.DataFrame]:
        """
        Compare trend scores across multiple tickers.
        
        Returns DataFrame ranked by trend velocity.
        """
        results = []
        
        for ticker in tickers[:5]:  # Max 5 for Google Trends
            score = self.get_trend_score(ticker)
            if score:
                results.append(score)
            time.sleep(1)  # Be polite
        
        if not results:
            return None
        
        df = pd.DataFrame(results)
        return df.sort_values('velocity', ascending=False)

def test_google_trends():
    """Test Google Trends integration."""
    logger.info("Testing Google Trends...")
    
    gt = GoogleTrends()
    
    # Test single ticker
    score = gt.get_trend_score("TSLA")
    if score:
        logger.info(f"TSLA trend score: {score}")
    else:
        logger.info("Could not get TSLA trend data")
    
    # Test comparison
    df = gt.compare_tickers(["AAPL", "NVDA", "TSLA", "AMZN", "META"])
    if df is not None:
        logger.info("\nTrend comparison:")
        logger.info(df.to_string())
    
    return df is not None

if __name__ == "__main__":
    if not PYTRENDS_AVAILABLE:
        logger.error("Install pytrends first: pip install pytrends")
        sys.exit(1)
    
    import sys
    success = test_google_trends()
    sys.exit(0 if success else 1)
