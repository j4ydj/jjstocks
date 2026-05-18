#!/usr/bin/env python3
"""
Railway / cron entry: scan top volatile names → one Telegram chain alert.
"""
import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_scan():
    """Run chain scan and send one Telegram message."""
    logger.info("Chain scan started %s", datetime.now().isoformat())

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in Railway")
        return False

    try:
        from daily_pipeline import run_pipeline, DAILY_OUTPUT, SCOREBOARD

        ok, plain = run_pipeline(send_telegram=True)
        logger.info("\n%s", plain[:4000])
        logger.info("Output: %s | Scoreboard: %s", DAILY_OUTPUT, SCOREBOARD)
        return ok
    except Exception as e:
        logger.error("Scan failed: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return False


def lambda_handler(event=None, context=None):
    ok = run_scan()
    return {"statusCode": 200 if ok else 500, "body": "OK" if ok else "FAIL"}


if __name__ == "__main__":
    success = run_scan()
    sys.exit(0 if success else 1)
