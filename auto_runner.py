#!/usr/bin/env python3
"""
AUTO RUNNER - Scheduled Edge System
====================================
Runs scans automatically on schedule.

Usage:
  python auto_runner.py --schedule daily
  python auto_runner.py --schedule market_open
  python auto_runner.py --once

Setup as cron job:
  0 9 * * 1-5 cd /Users/home/stocks && venv/bin/python auto_runner.py --schedule market_open
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_runner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SCHEDULES = {
    "market_open": {
        "hour": 9,
        "minute": 30,
        "days": [0, 1, 2, 3, 4],  # Mon-Fri
        "desc": "Market open (9:30 AM ET)"
    },
    "pre_market": {
        "hour": 8,
        "minute": 0,
        "days": [0, 1, 2, 3, 4],
        "desc": "Pre-market (8:00 AM ET)"
    },
    "midday": {
        "hour": 12,
        "minute": 0,
        "days": [0, 1, 2, 3, 4],
        "desc": "Mid-day (12:00 PM ET)"
    },
    "market_close": {
        "hour": 16,
        "minute": 0,
        "days": [0, 1, 2, 3, 4],
        "desc": "Market close (4:00 PM ET)"
    },
    "daily": {
        "hour": 7,
        "minute": 0,
        "days": [0, 1, 2, 3, 4, 5, 6],  # Every day
        "desc": "Daily morning (7:00 AM)"
    },
    "hourly": {
        "interval_minutes": 60,
        "desc": "Every hour"
    }
}

class AutoRunner:
    """Automated scan runner with scheduling."""
    
    def __init__(self):
        self.last_run = None
        self.run_count = 0
        self.state_file = "auto_runner_state.json"
        self.load_state()
    
    def load_state(self):
        """Load runner state."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                    self.run_count = state.get("run_count", 0)
                    self.last_run = state.get("last_run")
            except:
                pass
    
    def save_state(self):
        """Save runner state."""
        state = {
            "run_count": self.run_count,
            "last_run": datetime.now().isoformat(),
            "pid": os.getpid()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)
    
    def is_market_hours(self) -> bool:
        """Check if US market is open."""
        now = datetime.now()
        # Mon-Fri
        if now.weekday() > 4:
            return False
        # 9:30 AM - 4:00 PM ET (rough check)
        if now.hour < 9 or now.hour > 16:
            return False
        return True
    
    def run_scan(self, quick: bool = False) -> bool:
        """
        Execute scan and send alerts.
        
        Args:
            quick: If True, scan small universe (23 tickers)
        """
        logger.info("=" * 70)
        logger.info(f"  SCAN #{self.run_count + 1} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 70)
        
        try:
            if quick:
                # Fast scan - core universe
                logger.info("Running QUICK scan (23 tickers)...")
                from working_edge_system import WorkingEdgeSystem
                
                system = WorkingEdgeSystem()
                universe = [
                    "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
                    "GME", "AMC", "PLTR", "COIN", "HOOD", "SPY", "QQQ",
                    "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU", "RKLB"
                ]
                signals = system.scan(universe, min_score=2)
                
            else:
                # Full scan - priority universe
                logger.info("Running FULL scan (154 tickers)...")
                from market_wide_scanner import MarketWideScanner, get_priority_universe
                
                scanner = MarketWideScanner(delay=0.3)
                universe = get_priority_universe()
                signals = scanner.scan(universe, min_score=2)
            
            # Send Telegram alerts
            try:
                from telegram_alerts import TelegramBot
                bot = TelegramBot()
                
                if bot.enabled:
                    # Send summary
                    bot.send_daily_summary(signals, len(universe))
                    
                    # Send high confidence signals
                    high_conf = [s for s in signals if s.get("confidence") == "HIGH"]
                    if high_conf:
                        bot.send_message("🔥 <b>HIGH CONFIDENCE SIGNALS</b>")
                        for sig in high_conf[:3]:
                            bot.send_signal_alert(sig)
                    
                    logger.info("📤 Telegram alerts sent")
                else:
                    logger.info("📤 Telegram not configured (alerts disabled)")
            except Exception as e:
                logger.error(f"Telegram error: {e}")
            
            # Save results
            output = {
                "timestamp": datetime.now().isoformat(),
                "scan_type": "quick" if quick else "full",
                "universe_size": len(universe),
                "signals_found": len(signals),
                "signals": signals
            }
            
            filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(output, f, indent=2)
            
            logger.info(f"💾 Results saved to {filename}")
            
            # Update state
            self.run_count += 1
            self.save_state()
            
            logger.info(f"✅ Scan complete: {len(signals)} signals")
            return True
            
        except Exception as e:
            logger.error(f"❌ Scan failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def wait_until(self, hour: int, minute: int):
        """Wait until specific time."""
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if target < now:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        
        if wait_seconds > 0:
            logger.info(f"Waiting {wait_seconds/60:.0f} minutes until {hour:02d}:{minute:02d}...")
            time.sleep(wait_seconds)
    
    def run_scheduled(self, schedule_name: str):
        """Run on schedule."""
        if schedule_name not in SCHEDULES:
            logger.error(f"Unknown schedule: {schedule_name}")
            logger.info(f"Available: {list(SCHEDULES.keys())}")
            return False
        
        schedule = SCHEDULES[schedule_name]
        logger.info(f"Scheduled: {schedule['desc']}")
        
        try:
            while True:
                # Check if should run today
                now = datetime.now()
                if now.weekday() in schedule.get("days", [0, 1, 2, 3, 4, 5, 6]):
                    # Wait for scheduled time
                    self.wait_until(schedule["hour"], schedule["minute"])
                    
                    # Run scan
                    quick = schedule_name in ["pre_market", "midday"]
                    self.run_scan(quick=quick)
                    
                    # Wait a bit to avoid double-running
                    time.sleep(60)
                else:
                    # Skip today, wait until tomorrow
                    logger.info("Market closed today, waiting until tomorrow...")
                    time.sleep(3600)
                    
        except KeyboardInterrupt:
            logger.info("\n👋 Stopped by user")
            return True
        
        return True
    
    def run_loop(self, interval_minutes: int = 60):
        """Run in loop with fixed interval."""
        logger.info(f"Running every {interval_minutes} minutes...")
        
        try:
            while True:
                # Quick scan during market hours, full scan otherwise
                quick = self.is_market_hours()
                self.run_scan(quick=quick)
                
                logger.info(f"Sleeping {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("\n👋 Stopped by user")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto Edge Runner")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--quick", action="store_true", help="Quick scan (23 tickers)")
    parser.add_argument("--schedule", choices=list(SCHEDULES.keys()), help="Run on schedule")
    parser.add_argument("--loop", type=int, metavar="MINUTES", help="Run every N minutes")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    
    args = parser.parse_args()
    
    runner = AutoRunner()
    
    if args.once:
        success = runner.run_scan(quick=args.quick)
        sys.exit(0 if success else 1)
    
    elif args.schedule:
        runner.run_scheduled(args.schedule)
    
    elif args.loop:
        runner.run_loop(args.loop)
    
    else:
        # Default: run once
        runner.run_scan(quick=False)

if __name__ == "__main__":
    main()
