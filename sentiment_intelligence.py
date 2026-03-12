#!/usr/bin/env python3
"""
🎯 SENTIMENT INTELLIGENCE MODULE
================================

EDGE: Early momentum detection via social media before institutional awareness

DATA SOURCES:
• Reddit (r/wallstreetbets, r/stocks, r/investing)
• Social mention velocity (unusual attention spikes)
• Sentiment scoring (positive/negative trending)

VALUE: Reddit often leads institutional moves by 24-48 hours
WHY IT WORKS: Retail discovers opportunities before hedge funds
            (they don't monitor Reddit, we do)

Author: Revolutionary Trading System
Status: Phase 1 - Sentiment Edge
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import requests
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class SentimentSignal:
    """Sentiment analysis result"""
    ticker: str
    sentiment_score: float      # -1 to +1 (-1 = bearish, +1 = bullish)
    confidence: float            # 0 to 1
    mention_count: int           # Total mentions found
    velocity_score: float        # 0 to 1 (unusual mention spike)
    trending_rank: Optional[int] # Rank in trending (1 = #1 trending)
    key_phrases: List[str]       # What people are saying
    data_quality: float          # 0 to 1
    source_breakdown: Dict[str, int]  # Mentions by source
    reasoning: str               # Human readable explanation

class SentimentIntelligence:
    """
    Sentiment Intelligence Analyzer
    
    Tracks social media sentiment and mention velocity to detect
    early momentum before institutional awareness.
    """
    
    def __init__(self, config: Dict = None):
        """Initialize sentiment analyzer"""
        self.config = config or {}
        self.enabled = self.config.get('SENTIMENT_ENABLED', True)
        
        # Reddit configuration
        self.reddit_client_id = self.config.get('REDDIT_CLIENT_ID', '')
        self.reddit_client_secret = self.config.get('REDDIT_CLIENT_SECRET', '')
        self.reddit_user_agent = 'TradingBot/1.0'
        
        # Key subreddits to monitor
        self.subreddits = [
            'wallstreetbets',  # High volume, retail momentum
            'stocks',          # Serious discussion
            'investing',       # Longer-term views
            'StockMarket',     # General market
            'options'          # Options flow (can predict moves)
        ]
        
        # Cache to avoid re-fetching
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Initialize Reddit API if credentials provided
        self.reddit_available = bool(self.reddit_client_id and self.reddit_client_secret)
        if not self.reddit_available:
            logger.debug("Reddit API not configured - using fallback sentiment")
    
    def analyze(self, ticker: str) -> Optional[SentimentSignal]:
        """
        Analyze sentiment for a ticker
        
        Returns:
            SentimentSignal with all metrics, or None if analysis fails
        """
        if not self.enabled:
            return None
        
        # Check cache first
        cache_key = f"{ticker}_{int(time.time() / self.cache_ttl)}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Get Reddit sentiment (primary source)
            reddit_data = self._get_reddit_sentiment(ticker)
            
            # Get social velocity (mention spike detection)
            velocity_data = self._calculate_mention_velocity(ticker, reddit_data)
            
            # Calculate overall sentiment score
            sentiment_score = self._calculate_sentiment_score(reddit_data)
            
            # Extract key phrases
            key_phrases = self._extract_key_phrases(reddit_data)
            
            # Determine trending rank
            trending_rank = self._get_trending_rank(ticker, reddit_data)
            
            # Calculate confidence based on data quality
            confidence = self._calculate_confidence(reddit_data, velocity_data)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(
                sentiment_score, velocity_data, trending_rank, 
                reddit_data.get('mention_count', 0)
            )
            
            # Create signal
            signal = SentimentSignal(
                ticker=ticker,
                sentiment_score=sentiment_score,
                confidence=confidence,
                mention_count=reddit_data.get('mention_count', 0),
                velocity_score=velocity_data.get('velocity_score', 0),
                trending_rank=trending_rank,
                key_phrases=key_phrases,
                data_quality=reddit_data.get('data_quality', 0.5),
                source_breakdown=reddit_data.get('source_breakdown', {}),
                reasoning=reasoning
            )
            
            # Cache result
            self.cache[cache_key] = signal
            
            return signal
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed for {ticker}: {e}")
            return None
    
    def _get_reddit_sentiment(self, ticker: str) -> Dict:
        """Get Reddit sentiment data"""
        if self.reddit_available:
            return self._get_reddit_api_data(ticker)
        else:
            # Fallback: Use Reddit JSON API (no auth required, but limited)
            return self._get_reddit_json_data(ticker)
    
    def _get_reddit_json_data(self, ticker: str) -> Dict:
        """
        Get Reddit data using public JSON API (no auth required)
        This is our fallback method
        """
        mention_count = 0
        sentiment_scores = []
        source_breakdown = defaultdict(int)
        posts = []
        
        for subreddit in self.subreddits[:3]:  # Limit to top 3 for speed
            try:
                # Reddit provides JSON at .json endpoint
                url = f"https://www.reddit.com/r/{subreddit}/search.json"
                params = {
                    'q': ticker,
                    'sort': 'new',
                    'limit': 25,
                    't': 'day'  # Last 24 hours
                }
                headers = {'User-Agent': self.reddit_user_agent}
                
                response = requests.get(url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for post in data.get('data', {}).get('children', []):
                        post_data = post.get('data', {})
                        title = post_data.get('title', '').upper()
                        selftext = post_data.get('selftext', '').upper()
                        
                        # Check if ticker is mentioned
                        if ticker.upper() in title or ticker.upper() in selftext:
                            mention_count += 1
                            source_breakdown[subreddit] += 1
                            
                            # Simple sentiment analysis
                            text = (title + ' ' + selftext).lower()
                            sentiment = self._simple_sentiment_analysis(text)
                            sentiment_scores.append(sentiment)
                            
                            posts.append({
                                'title': post_data.get('title', ''),
                                'score': post_data.get('score', 0),
                                'num_comments': post_data.get('num_comments', 0)
                            })
                
                # Rate limiting - be respectful
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to fetch from r/{subreddit}: {e}")
                continue
        
        return {
            'mention_count': mention_count,
            'sentiment_scores': sentiment_scores,
            'source_breakdown': dict(source_breakdown),
            'posts': posts,
            'data_quality': min(1.0, mention_count / 10)  # Quality based on mentions
        }
    
    def _get_reddit_api_data(self, ticker: str) -> Dict:
        """
        Get Reddit data using official API (requires auth)
        This provides better rate limits and more data
        """
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                user_agent=self.reddit_user_agent
            )
            
            mention_count = 0
            sentiment_scores = []
            source_breakdown = defaultdict(int)
            posts = []
            
            for subreddit_name in self.subreddits:
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    
                    # Search for ticker mentions
                    for submission in subreddit.search(ticker, time_filter='day', limit=25):
                        mention_count += 1
                        source_breakdown[subreddit_name] += 1
                        
                        # Analyze sentiment
                        text = (submission.title + ' ' + submission.selftext).lower()
                        sentiment = self._simple_sentiment_analysis(text)
                        sentiment_scores.append(sentiment)
                        
                        posts.append({
                            'title': submission.title,
                            'score': submission.score,
                            'num_comments': submission.num_comments
                        })
                    
                except Exception as e:
                    logger.warning(f"Failed to search r/{subreddit_name}: {e}")
                    continue
            
            return {
                'mention_count': mention_count,
                'sentiment_scores': sentiment_scores,
                'source_breakdown': dict(source_breakdown),
                'posts': posts,
                'data_quality': min(1.0, mention_count / 10)
            }
            
        except ImportError:
            logger.warning("praw not installed, falling back to JSON API")
            return self._get_reddit_json_data(ticker)
        except Exception as e:
            logger.error(f"Reddit API error: {e}")
            return self._get_reddit_json_data(ticker)
    
    def _simple_sentiment_analysis(self, text: str) -> float:
        """
        Simple sentiment analysis using keyword matching
        Returns: -1 (bearish) to +1 (bullish)
        """
        # Bullish keywords
        bullish_keywords = [
            'buy', 'bull', 'bullish', 'moon', 'rocket', 'calls', 'long',
            'breakout', 'rally', 'pump', 'surge', 'spike', 'gain', 'profit',
            'undervalued', 'cheap', 'bargain', 'opportunity', 'growth'
        ]
        
        # Bearish keywords
        bearish_keywords = [
            'sell', 'bear', 'bearish', 'puts', 'short', 'crash', 'dump',
            'fall', 'drop', 'loss', 'overvalued', 'expensive', 'bubble',
            'risk', 'danger', 'warning', 'avoid'
        ]
        
        bullish_count = sum(1 for word in bullish_keywords if word in text)
        bearish_count = sum(1 for word in bearish_keywords if word in text)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0  # Neutral
        
        # Normalize to -1 to +1
        score = (bullish_count - bearish_count) / total
        return max(-1.0, min(1.0, score))
    
    def _calculate_sentiment_score(self, reddit_data: Dict) -> float:
        """Calculate overall sentiment score"""
        sentiment_scores = reddit_data.get('sentiment_scores', [])
        
        if not sentiment_scores:
            return 0  # Neutral if no data
        
        # Average sentiment
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        
        return avg_sentiment
    
    def _calculate_mention_velocity(self, ticker: str, reddit_data: Dict) -> Dict:
        """
        Calculate mention velocity (is this stock getting unusual attention?)
        
        Returns dict with velocity_score (0-1) and is_spiking (bool)
        """
        current_mentions = reddit_data.get('mention_count', 0)
        
        # Simple velocity: more mentions = higher velocity
        # In production, you'd compare to historical baseline
        velocity_score = min(1.0, current_mentions / 50)  # 50+ mentions = max velocity
        
        is_spiking = current_mentions > 20  # Arbitrary threshold
        
        return {
            'velocity_score': velocity_score,
            'is_spiking': is_spiking,
            'current_mentions': current_mentions
        }
    
    def _extract_key_phrases(self, reddit_data: Dict) -> List[str]:
        """Extract key phrases from posts"""
        posts = reddit_data.get('posts', [])
        
        if not posts:
            return []
        
        # Get titles of top posts (by score)
        sorted_posts = sorted(posts, key=lambda x: x.get('score', 0), reverse=True)
        key_phrases = [p['title'][:80] for p in sorted_posts[:3]]  # Top 3 titles
        
        return key_phrases
    
    def _get_trending_rank(self, ticker: str, reddit_data: Dict) -> Optional[int]:
        """Determine if ticker is trending and its rank"""
        mention_count = reddit_data.get('mention_count', 0)
        
        # Simple trending logic: if mentions > 30, consider it trending
        if mention_count > 30:
            return 1  # Top trending (simplified)
        elif mention_count > 20:
            return 2
        elif mention_count > 10:
            return 5
        else:
            return None  # Not trending
    
    def _calculate_confidence(self, reddit_data: Dict, velocity_data: Dict) -> float:
        """Calculate confidence in sentiment signal"""
        # Confidence based on:
        # 1. Number of mentions (more = better)
        # 2. Data quality
        # 3. Velocity (unusual attention increases confidence)
        
        mention_count = reddit_data.get('mention_count', 0)
        data_quality = reddit_data.get('data_quality', 0.5)
        velocity_score = velocity_data.get('velocity_score', 0)
        
        # Weighted confidence
        mention_confidence = min(1.0, mention_count / 20)  # 20+ mentions = full confidence
        
        confidence = (
            mention_confidence * 0.5 +
            data_quality * 0.3 +
            velocity_score * 0.2
        )
        
        return min(1.0, confidence)
    
    def _generate_reasoning(self, sentiment_score: float, velocity_data: Dict, 
                          trending_rank: Optional[int], mention_count: int) -> str:
        """Generate human-readable reasoning"""
        reasoning_parts = []
        
        # Sentiment
        if sentiment_score > 0.5:
            reasoning_parts.append(f"📈 BULLISH SENTIMENT: {sentiment_score:+.1%} (strong positive mentions)")
        elif sentiment_score > 0.2:
            reasoning_parts.append(f"📈 POSITIVE SENTIMENT: {sentiment_score:+.1%} (moderately positive)")
        elif sentiment_score > -0.2:
            reasoning_parts.append(f"📊 NEUTRAL SENTIMENT: {sentiment_score:+.1%} (mixed views)")
        elif sentiment_score > -0.5:
            reasoning_parts.append(f"📉 NEGATIVE SENTIMENT: {sentiment_score:+.1%} (moderately bearish)")
        else:
            reasoning_parts.append(f"📉 BEARISH SENTIMENT: {sentiment_score:+.1%} (strong negative mentions)")
        
        # Velocity
        if velocity_data.get('is_spiking'):
            reasoning_parts.append(f"⚡ UNUSUAL ATTENTION: {mention_count} mentions (significant spike)")
        elif mention_count > 10:
            reasoning_parts.append(f"👁️ MODERATE ATTENTION: {mention_count} mentions (above average)")
        else:
            reasoning_parts.append(f"👁️ LOW ATTENTION: {mention_count} mentions (below average)")
        
        # Trending
        if trending_rank:
            reasoning_parts.append(f"🔥 TRENDING: Rank #{trending_rank} on social media")
        
        return " || ".join(reasoning_parts)
    
    def health_check(self) -> bool:
        """Test if module is working"""
        try:
            # Try to analyze a known ticker
            result = self.analyze('AAPL')
            return result is not None
        except:
            return False

# Module-level cache to avoid recreating analyzer
_analyzer_cache = None

def get_sentiment_signal(ticker: str, config: Dict = None) -> Optional[SentimentSignal]:
    """
    Get sentiment signal for a ticker

    Args:
        ticker: Stock ticker symbol
        config: Configuration dict

    Returns:
        SentimentSignal or None if analysis fails
    """
    global _analyzer_cache
    if _analyzer_cache is None:
        _analyzer_cache = SentimentIntelligence(config)
    return _analyzer_cache.analyze(ticker)

if __name__ == "__main__":
    # Test the module
    print("🎯 Testing Sentiment Intelligence Module...")
    print("=" * 60)
    
    # Test with a popular stock
    test_tickers = ['TSLA', 'AAPL', 'GME']
    
    for ticker in test_tickers:
        print(f"\n📊 Analyzing {ticker}...")
        signal = get_sentiment_signal(ticker)
        
        if signal:
            print(f"   Sentiment: {signal.sentiment_score:+.1%}")
            print(f"   Confidence: {signal.confidence:.1%}")
            print(f"   Mentions: {signal.mention_count}")
            print(f"   Velocity: {signal.velocity_score:.1%}")
            if signal.trending_rank:
                print(f"   Trending: #{signal.trending_rank}")
            print(f"   Reasoning: {signal.reasoning}")
        else:
            print(f"   ❌ Analysis failed")
    
    print("\n" + "=" * 60)
    print("✅ Sentiment Intelligence test complete!")

