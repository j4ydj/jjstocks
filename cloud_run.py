#!/usr/bin/env python3
"""
CLOUD RUN - Entry Point for Cloud Deployment
=============================================
Optimized for Railway, Heroku, AWS Lambda, Google Cloud.

Environment Variables Required:
  TELEGRAM_BOT_TOKEN - Your bot token
  TELEGRAM_CHAT_ID - Your chat ID
"""
import os
import sys
import logging
from datetime import datetime

# Configure logging for cloud
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def health_check():
    """Quick health check - runs when Railway starts the service."""
    logger.info("Health check started")

    # Check environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False

    logger.info(f"Bot token: {token[:20]}...")
    logger.info(f"Chat ID: {chat_id}")

    # Test imports
    try:
        from working_edge_system import WorkingEdgeSystem
        from telegram_alerts import TelegramBot
        logger.info("✓ All imports successful")
        return True
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return False

def run_scan():
    """
    Run a quick scan and send Telegram alerts.
    This is the entry point for scheduled cloud runs.
    """
    logger.info("=" * 70)
    logger.info("CLOUD SCAN STARTED")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 70)

    # Check environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("Missing environment variables!")
        logger.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False

    logger.info(f"Bot configured: {token[:20]}...")
    logger.info(f"Chat ID: {chat_id}")

    try:
        # Import systems
        from working_edge_system import WorkingEdgeSystem
        from telegram_alerts import TelegramBot

        # Initialize
        system = WorkingEdgeSystem()
        bot = TelegramBot()

        # Define universe (cloud-optimized, smaller for speed)
        universe = [
            "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
            "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU",
            "GME", "AMC", "PLTR", "COIN", "HOOD", "RKLB",
            "SPY", "QQQ", "IWM", "ARKK"
        ]

        logger.info(f"Scanning {len(universe)} tickers...")

        # Run scan
        signals = system.scan(universe, min_score=2)

        # Process results
        longs = [s for s in signals if s.direction == "LONG"]
        shorts = [s for s in signals if s.direction == "SHORT"]
        avoids = [s for s in signals if s.direction == "AVOID"]

        logger.info(f"Results: {len(signals)} signals")
        logger.info(f"  LONG: {len(longs)}")
        logger.info(f"  SHORT: {len(shorts)}")
        logger.info(f"  AVOID: {len(avoids)}")

        # Send to Telegram
        if bot.enabled:
            bot.send_daily_summary(signals, len(universe))

            if longs:
                bot.send_message("🎯 <b>Top LONG Picks:</b>")
                for s in longs[:5]:
                    signal_dict = {
                        'ticker': s.ticker,
                        'score': s.score,
                        'direction': s.direction,
                        'confidence': s.confidence,
                        'sources': s.sources,
                        'catalyst': s.catalyst,
                        'price': s.price,
                        'signal_date': s.signal_date,
                        'scan_time': s.scan_time
                    }
                    bot.send_signal_alert(signal_dict)

            high_avoid = [s for s in avoids if s.confidence == "HIGH"][:3]
            if high_avoid:
                bot.send_message("⚠️ <b>HIGH RISK - AVOID:</b>")
                for s in high_avoid:
                    signal_dict = {
                        'ticker': s.ticker,
                        'score': s.score,
                        'direction': s.direction,
                        'confidence': s.confidence,
                        'sources': s.sources,
                        'catalyst': s.catalyst,
                        'price': s.price,
                        'signal_date': s.signal_date,
                        'scan_time': s.scan_time
                    }
                    bot.send_signal_alert(signal_dict)

            logger.info("Telegram alerts sent successfully")
        else:
            logger.warning("Telegram not configured - alerts not sent")

        logger.info("=" * 70)
        logger.info("CLOUD SCAN COMPLETE")
        logger.info("=" * 70)

        return True

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# For AWS Lambda / Google Cloud Functions
def lambda_handler(event=None, context=None):
    """AWS Lambda entry point."""
    success = run_scan()
    return {
        'statusCode': 200 if success else 500,
        'body': 'Scan complete' if success else 'Scan failed'
    }

# For Google Cloud Functions
def run(event=None, context=None):
    """Google Cloud Functions entry point."""
    return lambda_handler(event, context)

# For Railway / Heroku - when deployed as a service
if __name__ == "__main__":
    # Railway runs this as a service - do health check first
    logger.info("Starting trading bot service...")

    if health_check():
        logger.info("✓ Health check passed")
        # Run the scan
        success = run_scan()
        sys.exit(0 if success else 1)
    else:
        logger.error("✗ Health check failed")
        sys.exit(1)
