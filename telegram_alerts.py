#!/usr/bin/env python3
"""
TELEGRAM ALERTS - Automated Edge System
========================================
Sends trading signals to Telegram bot.

Setup:
1. Get bot token from @BotFather
2. Get chat ID from @userinfobot
3. Set environment variables or edit config below
4. Run: python telegram_alerts.py
"""
import os
import sys
import json
import logging
from datetime import datetime
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Configuration
# SECURITY NOTE: Use environment variables in production!
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

class TelegramBot:
    """Simple Telegram bot wrapper for trading alerts."""
    
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.enabled = bool(self.token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    
    def send_message(self, text: str) -> bool:
        """Send message to Telegram."""
        if not self.enabled:
            logger.info(f"[MOCK] Would send: {text[:50]}...")
            return True
        
        try:
            import urllib.request
            import urllib.parse
            
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            encoded_data = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=encoded_data, method="POST")
            
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_signal_alert(self, signal):
        """Format and send trading signal. Accepts dict or Signal object."""
        # Handle both dicts and Signal objects
        if isinstance(signal, dict):
            ticker = signal.get('ticker', 'UNKNOWN')
            score = signal.get('score', 0)
            direction = signal.get('direction', 'NEUTRAL')
            confidence = signal.get('confidence', 'LOW')
            sources = signal.get('sources', [])
            catalyst = signal.get('catalyst', 'N/A')
            price = signal.get('price', 'N/A')
            scan_time = signal.get('scan_time', datetime.now().strftime('%H:%M:%S'))
            signal_date = signal.get('signal_date', datetime.now().strftime('%Y-%m-%d'))
        else:
            # Signal object
            ticker = getattr(signal, 'ticker', 'UNKNOWN')
            score = getattr(signal, 'score', 0)
            direction = getattr(signal, 'direction', 'NEUTRAL')
            confidence = getattr(signal, 'confidence', 'LOW')
            sources = getattr(signal, 'sources', [])
            catalyst = getattr(signal, 'catalyst', 'N/A')
            price = getattr(signal, 'price', 'N/A')
            scan_time = getattr(signal, 'scan_time', datetime.now().strftime('%H:%M:%S'))
            signal_date = getattr(signal, 'signal_date', datetime.now().strftime('%Y-%m-%d'))

        emoji = {
            "LONG": "🚀",
            "SHORT": "🔻",
            "AVOID": "⚠️",
            "NEUTRAL": "⚪"
        }.get(direction, "📊")

        conf_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💤"}.get(confidence, "💤")

        # Format price
        if isinstance(price, (int, float)) and price is not None:
            price_str = f"${price:.2f}"
        else:
            price_str = str(price) if price else 'N/A'

        text = f"""{emoji} <b>{ticker}</b> | Score: {score:+d} | {price_str}

📅 Date: {signal_date}
⏰ Time: {scan_time}
📈 Direction: {direction}
🎯 Confidence: {confidence} {conf_emoji}
📊 Sources: {', '.join(sources)}

<b>Catalyst:</b>
{catalyst}

<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""

        return self.send_message(text)
    
    def send_daily_summary(self, signals, universe_size: int):
        """Send daily scan summary. Accepts list of dicts or Signal objects."""
        # Handle both dicts and Signal objects
        def get_direction(s):
            return s.get("direction") if isinstance(s, dict) else getattr(s, "direction", None)

        longs = [s for s in signals if get_direction(s) == "LONG"]
        shorts = [s for s in signals if get_direction(s) == "SHORT"]
        avoids = [s for s in signals if get_direction(s) == "AVOID"]

        text = f"""📊 <b>Daily Edge Scan Complete</b>

Scanned: {universe_size} tickers
Signals found: {len(signals)}

🚀 LONG: {len(longs)}
🔻 SHORT: {len(shorts)}
⚠️ AVOID: {len(avoids)}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""

        return self.send_message(text)

    def send_top_picks(self, signals, n: int = 5):
        """Send top N picks. Accepts list of dicts or Signal objects."""
        def get_direction(s):
            return s.get("direction") if isinstance(s, dict) else getattr(s, "direction", None)

        longs = [s for s in signals if get_direction(s) == "LONG"][:n]

        if not longs:
            return False

        lines = ["🎯 <b>TOP PICKS</b>\n"]
        for i, s in enumerate(longs, 1):
            if isinstance(s, dict):
                ticker = s.get('ticker', 'UNKNOWN')
                score = s.get('score', 0)
            else:
                ticker = getattr(s, 'ticker', 'UNKNOWN')
                score = getattr(s, 'score', 0)
            lines.append(f"{i}. {ticker} (Score: {score:+d})")

        text = "\n".join(lines)
        return self.send_message(text)

def run_and_alert():
    """Run full scan and send Telegram alerts."""
    logger.info("=" * 70)
    logger.info("  TELEGRAM EDGE ALERTS")
    logger.info("=" * 70)
    
    # Initialize bot
    bot = TelegramBot()
    
    if not bot.enabled:
        logger.info("\n⚠️  TELEGRAM NOT CONFIGURED")
        logger.info("\nTo enable alerts:")
        logger.info("1. Get bot token from @BotFather on Telegram")
        logger.info("2. Get your chat ID from @userinfobot")
        logger.info("3. Set environment variables:")
        logger.info("   export TELEGRAM_BOT_TOKEN='your_token'")
        logger.info("   export TELEGRAM_CHAT_ID='your_chat_id'")
        logger.info("\nOr edit telegram_alerts.py and set:")
        logger.info("   TELEGRAM_BOT_TOKEN = 'your_token'")
        logger.info("   TELEGRAM_CHAT_ID = 'your_chat_id'")
        logger.info("\nRunning in DRY RUN mode (no messages sent)")
    
    # Run scan
    logger.info("\nRunning market scan...")
    
    try:
        from market_wide_scanner import MarketWideScanner, get_priority_universe
        
        scanner = MarketWideScanner(delay=0.3)
        universe = get_priority_universe()
        signals = scanner.scan(universe, min_score=2)
        
        # Send summary
        bot.send_daily_summary(signals, len(universe))
        
        # Send top picks
        high_confidence = [s for s in signals if s.get("confidence") == "HIGH"]
        if high_confidence:
            bot.send_message("🔥 <b>HIGH CONFIDENCE SIGNALS</b>")
            for signal in high_confidence[:5]:
                bot.send_signal_alert(signal)
        
        # Send all strong signals
        strong = [s for s in signals if abs(s.get("score", 0)) >= 4]
        if strong:
            bot.send_top_picks(strong, n=5)
        
        logger.info(f"\n✅ Scan complete. {len(signals)} signals processed.")
        if bot.enabled:
            logger.info("📤 Alerts sent to Telegram")
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        bot.send_message(f"❌ <b>Scan Error</b>\n{str(e)[:200]}")
        return False
    
    return True

def setup_bot():
    """Interactive setup for Telegram bot."""
    logger.info("=" * 70)
    logger.info("  TELEGRAM BOT SETUP")
    logger.info("=" * 70)
    
    logger.info("\n1. Go to Telegram and search for @BotFather")
    logger.info("2. Start chat and send: /newbot")
    logger.info("3. Follow prompts to create bot")
    logger.info("4. Copy the bot token (looks like: 123456:ABC-DEF1234...)")
    logger.info("\n5. Search for @userinfobot")
    logger.info("6. Copy your chat ID (looks like: 123456789)")
    logger.info("\n6. Set environment variables:")
    logger.info("   export TELEGRAM_BOT_TOKEN='your_token_here'")
    logger.info("   export TELEGRAM_CHAT_ID='your_chat_id'")
    logger.info("\n7. Run: python telegram_alerts.py --test")

def test_connection():
    """Test Telegram connection."""
    bot = TelegramBot()
    
    if not bot.enabled:
        logger.error("Bot not configured. See setup instructions.")
        return False
    
    success = bot.send_message("🧪 <b>Test Message</b>\nBot is working!")
    
    if success:
        logger.info("✅ Test message sent successfully!")
    else:
        logger.error("❌ Failed to send test message")
    
    return success

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Edge Alerts")
    parser.add_argument("--setup", action="store_true", help="Show setup instructions")
    parser.add_argument("--test", action="store_true", help="Test connection")
    parser.add_argument("--run", action="store_true", help="Run scan and send alerts")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_bot()
    elif args.test:
        test_connection()
    else:
        run_and_alert()

if __name__ == "__main__":
    main()
