#!/usr/bin/env python3
"""
CLOUD RUN v2 - Railway/Lambda Entry Point
==========================================
Runs edge scan, sends only actionable trades to Telegram.
"""
import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_scan():
    """Run full scan and send trade alerts to Telegram."""
    logger.info("=" * 60)
    logger.info("EDGE SCAN STARTED")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return False

    try:
        from working_edge_system import EdgeSystem
        from telegram_alerts import TelegramBot

        system = EdgeSystem(min_conviction=3)
        bot = TelegramBot()

        trades = system.scan()

        logger.info(f"Results: {len(trades)} trades")

        if bot.enabled:
            # Send summary
            from working_edge_system import UNIVERSE
            bot.send_scan_summary(trades, len(UNIVERSE))

            # Send each trade
            for trade in trades:
                bot.send_trade(trade)

            logger.info("Telegram alerts sent")
        else:
            logger.warning("Telegram not configured")

        logger.info("=" * 60)
        logger.info("SCAN COMPLETE")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def lambda_handler(event=None, context=None):
    success = run_scan()
    return {
        'statusCode': 200 if success else 500,
        'body': 'OK' if success else 'FAIL'
    }


if __name__ == "__main__":
    logger.info("Starting edge scanner...")
    success = run_scan()
    sys.exit(0 if success else 1)
