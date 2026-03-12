#!/usr/bin/env python3
"""
📊 TRADE TRACKER MODULE
======================

Logs all approved trades and tracks their performance over time.

FEATURES:
• Logs ticker, entry price, date/time, signal type
• Tracks current price vs entry price
• Calculates P&L % for each trade
• Shows win rate and average return
• Exports to CSV for analysis

EDGE VALIDATION:
This is how you validate which edge sources actually work!
Track performance → Refine thresholds → Improve accuracy

Author: Revolutionary Trading System
Status: Essential for system improvement
"""

import logging
import csv
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import yfinance as yf
import os

logger = logging.getLogger(__name__)

@dataclass
class Trade:
    """A tracked trade"""
    id: str                    # Unique ID
    ticker: str               # Stock ticker
    entry_price: float        # Price when signal generated
    entry_date: str           # ISO format date/time
    signal_type: str          # BUY, SELL, STRONG_BUY, etc.
    confidence: float         # 0-1 confidence
    edge_sources: str         # Which sources approved it
    comment: str              # Analysis/reasoning
    
    # Performance tracking
    current_price: float = 0.0
    current_date: str = ""
    pnl_percent: float = 0.0
    days_held: int = 0
    status: str = "OPEN"      # OPEN, WINNER, LOSER

class TradeTracker:
    """
    Track all approved trades and their performance
    """
    
    def __init__(self, csv_file: str = "trades_history.csv"):
        """Initialize trade tracker"""
        self.csv_file = csv_file
        self.trades = []
        
        # Load existing trades
        self._load_trades()
    
    def log_trade(self, ticker: str, entry_price: float, signal_type: str,
                  confidence: float, edge_sources: List[str], comment: str) -> str:
        """
        Log a new trade
        
        Returns:
            Trade ID
        """
        try:
            # Generate unique ID
            trade_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create trade
            trade = Trade(
                id=trade_id,
                ticker=ticker,
                entry_price=entry_price,
                entry_date=datetime.now().isoformat(),
                signal_type=signal_type,
                confidence=confidence,
                edge_sources=", ".join(edge_sources),
                comment=comment
            )
            
            # Add to list
            self.trades.append(trade)
            
            # Save to CSV
            self._save_trade(trade)
            
            logger.info(f"Trade logged: {trade_id}")
            
            return trade_id
            
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
            return ""
    
    def update_trade_performance(self, trade_id: str) -> Optional[Dict]:
        """
        Update performance for a specific trade
        
        Returns:
            Updated trade info
        """
        try:
            # Find trade
            trade = next((t for t in self.trades if t.id == trade_id), None)
            if not trade:
                return None
            
            # Get current price
            current_price = self._get_current_price(trade.ticker)
            if current_price is None:
                return None
            
            # Calculate performance
            entry_date = datetime.fromisoformat(trade.entry_date)
            days_held = (datetime.now() - entry_date).days
            
            # Calculate P&L based on signal type
            if trade.signal_type in ["BUY", "STRONG_BUY"]:
                pnl_percent = ((current_price - trade.entry_price) / trade.entry_price) * 100
            elif trade.signal_type in ["SELL", "STRONG_SELL"]:
                pnl_percent = ((trade.entry_price - current_price) / trade.entry_price) * 100
            else:
                pnl_percent = 0
            
            # Update trade
            trade.current_price = current_price
            trade.current_date = datetime.now().isoformat()
            trade.pnl_percent = pnl_percent
            trade.days_held = days_held
            
            # Determine status
            if days_held >= 1:  # Only mark after holding at least 1 day
                if pnl_percent > 2:
                    trade.status = "WINNER"
                elif pnl_percent < -2:
                    trade.status = "LOSER"
                else:
                    trade.status = "OPEN"
            
            # Save updates
            self._save_all_trades()
            
            return asdict(trade)
            
        except Exception as e:
            logger.error(f"Failed to update trade {trade_id}: {e}")
            return None
    
    def update_all_trades(self) -> int:
        """
        Update performance for all open trades
        
        Returns:
            Number of trades updated
        """
        updated = 0
        
        for trade in self.trades:
            if trade.status == "OPEN" or True:  # Update all for latest prices
                result = self.update_trade_performance(trade.id)
                if result:
                    updated += 1
        
        return updated
    
    def get_trade_summary(self) -> Dict:
        """Get summary statistics of all trades"""
        try:
            if not self.trades:
                return {
                    'total_trades': 0,
                    'open_trades': 0,
                    'closed_trades': 0,
                    'winners': 0,
                    'losers': 0,
                    'win_rate': 0,
                    'avg_return': 0,
                    'total_return': 0
                }
            
            # Update all trades first
            self.update_all_trades()
            
            total = len(self.trades)
            open_trades = sum(1 for t in self.trades if t.status == "OPEN")
            winners = sum(1 for t in self.trades if t.status == "WINNER")
            losers = sum(1 for t in self.trades if t.status == "LOSER")
            closed = winners + losers
            
            win_rate = (winners / closed * 100) if closed > 0 else 0
            
            # Calculate returns
            returns = [t.pnl_percent for t in self.trades if t.pnl_percent != 0]
            avg_return = sum(returns) / len(returns) if returns else 0
            total_return = sum(returns)
            
            return {
                'total_trades': total,
                'open_trades': open_trades,
                'closed_trades': closed,
                'winners': winners,
                'losers': losers,
                'win_rate': win_rate,
                'avg_return': avg_return,
                'total_return': total_return
            }
            
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return {}
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get most recent trades"""
        try:
            # Update all trades
            self.update_all_trades()
            
            # Sort by entry date (most recent first)
            sorted_trades = sorted(
                self.trades,
                key=lambda t: t.entry_date,
                reverse=True
            )
            
            return [asdict(t) for t in sorted_trades[:limit]]
            
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []
    
    def get_trades_by_edge_source(self, edge_source: str) -> List[Dict]:
        """Get trades approved by a specific edge source"""
        try:
            matching_trades = [
                t for t in self.trades 
                if edge_source.lower() in t.edge_sources.lower()
            ]
            
            return [asdict(t) for t in matching_trades]
            
        except Exception as e:
            logger.error(f"Failed to filter trades: {e}")
            return []
    
    def generate_performance_report(self) -> str:
        """Generate a detailed performance report"""
        try:
            summary = self.get_trade_summary()
            recent = self.get_recent_trades(5)
            
            report = f"""
📊 TRADE PERFORMANCE REPORT
{'='*60}

SUMMARY:
• Total Trades: {summary['total_trades']}
• Open: {summary['open_trades']} | Winners: {summary['winners']} | Losers: {summary['losers']}
• Win Rate: {summary['win_rate']:.1f}%
• Average Return: {summary['avg_return']:+.2f}%
• Total Return: {summary['total_return']:+.2f}%

RECENT TRADES (Last 5):
"""
            
            for i, trade in enumerate(recent, 1):
                status_emoji = "🟢" if trade['status'] == "WINNER" else "🔴" if trade['status'] == "LOSER" else "⚪"
                
                report += f"""
{i}. {status_emoji} {trade['ticker']} - {trade['signal_type']}
   Entry: ${trade['entry_price']:.2f} on {trade['entry_date'][:10]}
   Current: ${trade['current_price']:.2f} ({trade['pnl_percent']:+.2f}%)
   Days: {trade['days_held']} | Edge: {trade['edge_sources'][:30]}...
   Comment: {trade['comment'][:60]}...
"""
            
            report += f"\n{'='*60}\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return "❌ Failed to generate report"
    
    def _get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for a ticker"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1d')
            
            if hist.empty:
                return None
            
            return hist['Close'].iloc[-1]
            
        except Exception as e:
            logger.error(f"Failed to get price for {ticker}: {e}")
            return None
    
    def _load_trades(self):
        """Load trades from CSV"""
        try:
            if not os.path.exists(self.csv_file):
                # Create new file with headers
                self._create_csv()
                return
            
            with open(self.csv_file, 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    trade = Trade(
                        id=row['id'],
                        ticker=row['ticker'],
                        entry_price=float(row['entry_price']),
                        entry_date=row['entry_date'],
                        signal_type=row['signal_type'],
                        confidence=float(row['confidence']),
                        edge_sources=row['edge_sources'],
                        comment=row['comment'],
                        current_price=float(row.get('current_price', 0)),
                        current_date=row.get('current_date', ''),
                        pnl_percent=float(row.get('pnl_percent', 0)),
                        days_held=int(row.get('days_held', 0)),
                        status=row.get('status', 'OPEN')
                    )
                    
                    self.trades.append(trade)
            
            logger.info(f"Loaded {len(self.trades)} trades from {self.csv_file}")
            
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
    
    def _create_csv(self):
        """Create new CSV file with headers"""
        try:
            with open(self.csv_file, 'w', newline='') as f:
                fieldnames = [
                    'id', 'ticker', 'entry_price', 'entry_date', 'signal_type',
                    'confidence', 'edge_sources', 'comment', 'current_price',
                    'current_date', 'pnl_percent', 'days_held', 'status'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
            
            logger.info(f"Created new trades file: {self.csv_file}")
            
        except Exception as e:
            logger.error(f"Failed to create CSV: {e}")
    
    def _save_trade(self, trade: Trade):
        """Append a single trade to CSV"""
        try:
            file_exists = os.path.exists(self.csv_file)
            
            with open(self.csv_file, 'a', newline='') as f:
                fieldnames = [
                    'id', 'ticker', 'entry_price', 'entry_date', 'signal_type',
                    'confidence', 'edge_sources', 'comment', 'current_price',
                    'current_date', 'pnl_percent', 'days_held', 'status'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(asdict(trade))
            
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
    
    def _save_all_trades(self):
        """Save all trades to CSV (overwrites file)"""
        try:
            with open(self.csv_file, 'w', newline='') as f:
                fieldnames = [
                    'id', 'ticker', 'entry_price', 'entry_date', 'signal_type',
                    'confidence', 'edge_sources', 'comment', 'current_price',
                    'current_date', 'pnl_percent', 'days_held', 'status'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for trade in self.trades:
                    writer.writerow(asdict(trade))
            
        except Exception as e:
            logger.error(f"Failed to save all trades: {e}")

# Global instance
_tracker = None

def _get_tracker_csv_path() -> str:
    """Read the configured CSV path when available."""
    try:
        with open("trading_config.json", "r") as f:
            config = json.load(f)
    except Exception:
        return "trades_history.csv"

    return (
        config.get("TRADES_CSV_FILE")
        or config.get("SIGNALS_CSV_FILE")
        or "trades_history.csv"
    )

def get_tracker() -> TradeTracker:
    """Get global trade tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = TradeTracker(csv_file=_get_tracker_csv_path())
    return _tracker

def log_approved_trade(ticker: str, entry_price: float, signal_type: str,
                       confidence: float, edge_sources: List[str], comment: str) -> str:
    """
    Log an approved trade (simple interface)
    
    Returns:
        Trade ID
    """
    tracker = get_tracker()
    return tracker.log_trade(ticker, entry_price, signal_type, confidence, edge_sources, comment)

def get_performance_report() -> str:
    """Get performance report (simple interface)"""
    tracker = get_tracker()
    return tracker.generate_performance_report()

if __name__ == "__main__":
    # Test the module
    print("📊 Testing Trade Tracker Module...")
    print("=" * 60)
    
    tracker = TradeTracker(csv_file="test_trades.csv")
    
    # Log some test trades
    print("\n1. Logging test trades...")
    
    tracker.log_trade(
        ticker="AAPL",
        entry_price=175.50,
        signal_type="BUY",
        confidence=0.75,
        edge_sources=["Technical", "Sentiment", "Momentum"],
        comment="Strong bull momentum (42.3), positive sentiment (+15%), MACD golden cross"
    )
    
    tracker.log_trade(
        ticker="TSLA",
        entry_price=242.50,
        signal_type="STRONG_BUY",
        confidence=0.85,
        edge_sources=["Momentum", "Sentiment"],
        comment="Green diamond signal, trending #1 on Reddit, institutional buying"
    )
    
    print(f"   ✅ Logged {len(tracker.trades)} trades")
    
    # Update performance
    print("\n2. Updating trade performance...")
    updated = tracker.update_all_trades()
    print(f"   ✅ Updated {updated} trades")
    
    # Generate report
    print("\n3. Generating performance report...")
    report = tracker.generate_performance_report()
    print(report)
    
    print("=" * 60)
    print("✅ Trade Tracker test complete!")
    
    # Clean up test file
    if os.path.exists("test_trades.csv"):
        os.remove("test_trades.csv")



