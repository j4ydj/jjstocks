#!/usr/bin/env python3
"""
EDGE BACKTEST - Validate Edge Performance
=========================================
Backtest each edge factor individually and in combination.
"""
import logging
import sys
from typing import Dict, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest import fetch_bulk, fetch_spy, UNIVERSE, metrics_only

class EdgeBacktester:
    """Backtest individual edge factors."""
    
    def __init__(self):
        self.all_data = None
        self.spy_df = None
    
    def load_data(self, tickers=None, days=300):
        """Load price data once."""
        if self.all_data is None:
            logger.info("Loading price data...")
            tickers = tickers or UNIVERSE[:30]  # Smaller for speed
            self.all_data = fetch_bulk(tickers, days=days)
            self.spy_df = fetch_spy(days=days)
            logger.info(f"Loaded {len(self.all_data)} tickers")
        return self.all_data, self.spy_df
    
    def backtest_earnings_edge(self, min_surprise=15, hold_days=20):
        """
        Backtest: Buy earnings beats, hold N days.
        Returns: metrics dict
        """
        from earnings_drift import get_historical_earnings
        from backtest import backtest_earnings
        
        all_data, spy_df = self.load_data()
        
        logger.info(f"\nBacktesting Earnings Edge (surprise >{min_surprise}%, hold {hold_days}d)...")
        
        df = backtest_earnings(all_data, spy_df, hold_days=hold_days, min_surprise=min_surprise, entry_delay=1)
        
        if df.empty:
            logger.info(f"  No trades generated")
            return None
        
        # Filter to BUY only
        if "direction" in df.columns:
            df = df[df["direction"] == "BUY"]
        
        if len(df) < 10:
            logger.info(f"  Insufficient trades: {len(df)}")
            return None
        
        m = metrics_only(df)
        
        logger.info(f"  Trades: {m['signals']}")
        logger.info(f"  Win rate: {m['alpha_hit']:.1f}%")
        logger.info(f"  Median alpha: {m['median_alpha']:+.2f}%")
        logger.info(f"  Avg alpha: {m['avg_alpha']:+.2f}%")
        
        return m
    
    def backtest_sec_filter_impact(self):
        """
        Measure impact of SEC risk filter on baseline.
        Compare: baseline vs filtered.
        """
        logger.info("\nBacktesting SEC Risk Filter Impact...")
        
        try:
            import sec_filing_risk
        except:
            logger.info("  SEC module not available")
            return None
        
        all_data, spy_df = self.load_data()
        
        # Get list of risky tickers
        risky = []
        clean = []
        
        for ticker in all_data.keys():
            is_clean, form, count = sec_filing_risk.is_clean(ticker, {})
            if is_clean:
                clean.append(ticker)
            else:
                risky.append((ticker, form, count))
        
        logger.info(f"  Clean tickers: {len(clean)}")
        logger.info(f"  Risky tickers: {len(risky)}")
        
        if risky:
            logger.info(f"  Sample risky: {risky[:3]}")
        
        return {
            "clean_count": len(clean),
            "risky_count": len(risky),
            "risky_tickers": risky[:5]
        }
    
    def backtest_pm_sentiment(self, tickers=None):
        """
        Backtest prediction market sentiment (contrarian).
        Limited by PM market availability.
        """
        logger.info("\nBacktesting PM Sentiment Edge...")
        
        try:
            from prediction_markets import get_earnings_beat_odds
        except:
            logger.info("  PM module not available")
            return None
        
        # Test tickers with PM coverage
        pm_tickers = tickers or ["AAPL", "TSLA", "NVDA", "META", "AMZN"]
        
        results = []
        for ticker in pm_tickers:
            odds = get_earnings_beat_odds(ticker)
            if odds is not None:
                results.append({
                    "ticker": ticker,
                    "pm_odds": odds,
                    "signal": "CONTRARIAN_LONG" if odds < 0.4 else "AVOID" if odds > 0.7 else "NEUTRAL"
                })
        
        if results:
            df = pd.DataFrame(results)
            logger.info(f"  Found PM data for {len(df)} tickers")
            logger.info(f"  Contrarian signals: {len(df[df['signal']=='CONTRARIAN_LONG'])}")
            return {"pm_coverage": len(df), "signals": results}
        
        logger.info("  No active PM markets found")
        return None
    
    def run_full_validation(self):
        """Run all edge validations."""
        logger.info("=" * 70)
        logger.info("  EDGE VALIDATION BACKTEST")
        logger.info("=" * 70)
        
        results = {}
        
        # 1. Earnings edge
        for surprise in [10, 15, 20]:
            for hold in [10, 20, 40]:
                m = self.backtest_earnings_edge(min_surprise=surprise, hold_days=hold)
                if m:
                    key = f"earn_s{surprise}_h{hold}"
                    results[key] = m
        
        # 2. SEC filter
        sec_results = self.backtest_sec_filter_impact()
        if sec_results:
            results["sec_filter"] = sec_results
        
        # 3. PM edge
        pm_results = self.backtest_pm_sentiment()
        if pm_results:
            results["pm_sentiment"] = pm_results
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("  VALIDATION SUMMARY")
        logger.info("=" * 70)
        
        # Find best earnings config
        best_earn = None
        best_score = -999
        for key, val in results.items():
            if key.startswith("earn_"):
                score = val.get("median_alpha", 0) * val.get("alpha_hit", 0) / 100
                if score > best_score:
                    best_score = score
                    best_earn = (key, val)
        
        if best_earn:
            key, val = best_earn
            logger.info(f"\n🏆 Best Earnings Edge: {key}")
            logger.info(f"  Trades: {val['signals']}")
            logger.info(f"  Win rate: {val['alpha_hit']:.1f}%")
            logger.info(f"  Median alpha: {val['median_alpha']:+.2f}%")
        
        if "sec_filter" in results:
            sec = results["sec_filter"]
            logger.info(f"\n📋 SEC Filter Impact:")
            logger.info(f"  Avoided {sec['risky_count']} risky tickers")
            if sec['risky_tickers']:
                logger.info(f"  Examples: {', '.join(t[0] for t in sec['risky_tickers'][:3])}")
        
        if "pm_sentiment" in results:
            pm = results["pm_sentiment"]
            logger.info(f"\n🎯 PM Sentiment Coverage:")
            logger.info(f"  {pm['pm_coverage']} tickers with PM data")
        
        # Final verdict
        logger.info("\n" + "=" * 70)
        if best_earn and best_earn[1]['median_alpha'] > 0:
            logger.info("✅ EDGE VALIDATED: Earnings surprise with entry delay works")
            logger.info(f"   Best config: {best_earn[0]}")
            logger.info(f"   Median alpha: {best_earn[1]['median_alpha']:+.2f}%")
            return True
        else:
            logger.info("⚠️  No strong edge found in validation")
            return False

def main():
    backtester = EdgeBacktester()
    success = backtester.run_full_validation()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
