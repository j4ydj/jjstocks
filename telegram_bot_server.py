#!/usr/bin/env python3
"""
TELEGRAM BOT SERVER - Remote Control
=====================================
Run scans via Telegram commands.

Commands:
  /start - Welcome message
  /quick - Quick scan (23 tickers, 2 min)
  /full - Full scan (154 tickers, 7 min)
  /all - Complete scan (362 tickers, 15 min)
  /longs - Show top long signals
  /shorts - Show top short signals
  /status - Bot status
  /help - Show commands

Usage:
  python telegram_bot_server.py

The bot runs continuously and responds to your Telegram messages.
"""
import os
import sys
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

class TelegramBotServer:
    """Bot that listens for commands and runs scans."""
    
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.running = False
        self.last_scan_results = []
        self.last_scan_meta = None
        self.command_handlers = {
            '/start': self.cmd_start,
            '/help': self.cmd_help,
            '/scan': self.cmd_scan,
            '/quick': self.cmd_quick,
            '/plays': self.cmd_plays,
            '/full': self.cmd_scan,
            '/all': self.cmd_scan,
            '/longs': self.cmd_plays,
            '/shorts': self.cmd_shorts,
            '/status': self.cmd_status,
        }
    
    def api_call(self, method: str, params: Dict = None) -> Optional[Dict]:
        """Make API call to Telegram."""
        try:
            import urllib.request
            import urllib.parse
            
            url = f"{self.base_url}/{method}"
            if params:
                data = urllib.parse.urlencode(params).encode()
                req = urllib.request.Request(url, data=data, method="POST")
            else:
                req = urllib.request.Request(url)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                return result.get('result')
        except Exception as e:
            logger.error(f"API error: {e}")
            return None
    
    def send_message(self, chat_id: str, text: str) -> bool:
        """Send message to user."""
        result = self.api_call('sendMessage', {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        })
        return result is not None
    
    def get_updates(self) -> List[Dict]:
        """Get new messages from Telegram."""
        result = self.api_call('getUpdates', {
            'offset': self.last_update_id + 1,
            'limit': 10
        })
        return result or []
    
    def handle_command(self, chat_id: str, command: str, username: str):
        """Process user command."""
        logger.info(f"Command from {username}: {command}")
        
        handler = self.command_handlers.get(command.lower())
        if handler:
            handler(chat_id)
        else:
            self.send_message(chat_id, f"Unknown command: {command}\nTry /help")
    
    # ===== Command Handlers =====
    
    def cmd_start(self, chat_id: str):
        """Welcome message."""
        welcome = """🤖 <b>Momentum Chain Bot</b>

Top volatile names → upstream/downstream map → trade plays.

<b>Commands:</b>
/scan - Full chain + plays (~3 min)
/quick - Top 5 volatile only (~2 min)
/plays - Show plays from last scan
/status - Bot status
/help - Commands"""
        self.send_message(chat_id, welcome)
    
    def cmd_help(self, chat_id: str):
        """Help message."""
        help_text = """📋 <b>Commands</b>

/scan - Chain map + trade plays (top 10 volatile)
/quick - Faster scan (top 5)
/plays - Plays from last /scan
/status - Status
/help - This message"""
        self.send_message(chat_id, help_text)
    
    def _run_momentum_scan(self, chat_id: str, top_n: int = 10):
        from momentum_plays import scan_and_save
        from telegram_alerts import TelegramBot

        result, plays, path = scan_and_save(top_n=top_n)
        self.last_scan_results = plays
        self.last_scan_meta = result

        bot = TelegramBot()
        if bot.enabled:
            bot.send_momentum_scan(result)
            for pl in plays[:5]:
                bot.send_trade_play(pl)

        buys = [p for p in plays if p.direction == "BUY"]
        shorts = [p for p in plays if p.direction == "SHORT"]
        self.send_message(
            chat_id,
            f"✅ <b>Scan done</b>\nPlays: {len(plays)} (BUY {len(buys)}, SHORT {len(shorts)})\n"
            f"Saved: {path}\nUse /plays for details.",
        )

    def cmd_quick(self, chat_id: str):
        self.send_message(chat_id, "⏳ Quick scan (top 5 volatile)...")
        try:
            self._run_momentum_scan(chat_id, top_n=5)
        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            self.send_message(chat_id, f"❌ Scan failed: {str(e)[:100]}")

    def cmd_scan(self, chat_id: str):
        self.send_message(chat_id, "⏳ Momentum chain scan (~3 min)...")
        def run():
            try:
                self._run_momentum_scan(chat_id, top_n=10)
            except Exception as e:
                self.send_message(chat_id, f"❌ {str(e)[:100]}")
        threading.Thread(target=run, daemon=True).start()

    def cmd_full(self, chat_id: str):
        self.cmd_scan(chat_id)

    def cmd_all(self, chat_id: str):
        self.cmd_scan(chat_id)

    def cmd_plays(self, chat_id: str):
        plays = self.last_scan_results or []
        if not plays:
            self.send_message(chat_id, "No plays yet. Run /scan first.")
            return
        from telegram_alerts import TelegramBot
        bot = TelegramBot()
        for pl in plays[:5]:
            bot.send_trade_play(pl)

    def cmd_longs(self, chat_id: str):
        self.cmd_plays(chat_id)

    def cmd_shorts(self, chat_id: str):
        plays = [p for p in (self.last_scan_results or []) if getattr(p, "direction", None) == "SHORT"]
        if not plays:
            self.send_message(chat_id, "No SHORT plays in last scan.")
            return
        from telegram_alerts import TelegramBot
        bot = TelegramBot()
        for pl in plays[:3]:
            bot.send_trade_play(pl)
    
    def cmd_status(self, chat_id: str):
        """Show bot status."""
        meta = self.last_scan_meta
        when = getattr(meta, "scan_time", "never") if meta else "never"
        status = f"""📊 <b>Momentum Chain Bot</b>

✅ Online
Last scan: {when}
Plays cached: {len(self.last_scan_results or [])}

Send /scan or /quick to run."""
        self.send_message(chat_id, status)
    
    # ===== Main Loop =====
    
    def run(self):
        """Main loop - polls for messages."""
        logger.info("=" * 70)
        logger.info("TELEGRAM BOT SERVER STARTED")
        logger.info("=" * 70)
        logger.info(f"Token: {self.token[:20]}...")
        logger.info("Waiting for commands...")
        logger.info("")
        
        self.running = True
        
        while self.running:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.last_update_id = update['update_id']
                    
                    if 'message' in update:
                        message = update['message']
                        chat_id = str(message['chat']['id'])
                        
                        if 'text' in message:
                            text = message['text']
                            username = message['from'].get('username', 'unknown')
                            
                            # Only respond to commands
                            if text.startswith('/'):
                                self.handle_command(chat_id, text.split()[0], username)
                
                # Poll every 2 seconds
                time.sleep(2)
                
            except KeyboardInterrupt:
                logger.info("\nStopping bot...")
                self.running = False
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(5)

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ No bot token configured!")
        print("Set TELEGRAM_BOT_TOKEN environment variable")
        sys.exit(1)
    
    bot = TelegramBotServer()
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")

if __name__ == "__main__":
    main()
