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
        from chain_ping import scan_and_notify, format_plain_ping

        from chain_ping import chains_with_moves
        from chain_setups import find_all_setups

        result, message, sent = scan_and_notify(send_telegram=True)
        setups = find_all_setups(chains_with_moves(result), result.price_cache)
        if message:
            logger.info("\n%s", format_plain_ping(result, message))
        else:
            logger.info("No actionable setups — Telegram skipped (logged to trade_setups.jsonl)")
        if sent:
            logger.info("Telegram sent (%d setup(s))", len(setups))
        elif setups:
            logger.warning("Setups found (%d) but Telegram not sent", len(setups))
        else:
            logger.info("Quiet scan: 0 setups — heartbeat still logged")

        from trade_tracker import SETUP_FILE
        logger.info("Trade log: %s", SETUP_FILE)
        return True
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
