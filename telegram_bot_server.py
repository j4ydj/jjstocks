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
        self.command_handlers = {
            '/start': self.cmd_start,
            '/help': self.cmd_help,
            '/quick': self.cmd_quick,
            '/full': self.cmd_full,
            '/all': self.cmd_all,
            '/longs': self.cmd_longs,
            '/shorts': self.cmd_shorts,
            '/status': self.cmd_status,
            '/scan': self.cmd_quick,  # Alias
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
        welcome = """🤖 <b>Trading Bot Activated!</b>

I'll scan the market for edge opportunities.

<b>Commands:</b>
/quick - Fast scan (23 tickers, 2 min)
/full - Full scan (154 tickers, 7 min)
/all - Complete scan (362 tickers, 15 min)
/longs - Top buy signals
/shorts - Top sell signals
/status - Bot status
/help - Show all commands

Just send a command to run a scan."""
        self.send_message(chat_id, welcome)
    
    def cmd_help(self, chat_id: str):
        """Help message."""
        help_text = """📋 <b>Available Commands</b>

<b>Scans:</b>
/quick - 23 priority tickers (~2 min)
/full - 154 high-potential tickers (~7 min)
/all - Complete market scan 362 tickers (~15 min)

<b>Results:</b>
/longs - Show latest LONG signals
/shorts - Show latest SHORT signals

<b>Info:</b>
/status - Bot status & last scan
/help - This message

<b>Tip:</b> Use /quick for frequent updates, /full for daily analysis."""
        self.send_message(chat_id, help_text)
    
    def cmd_quick(self, chat_id: str):
        """Run quick scan."""
        self.send_message(chat_id, "⏳ Running quick scan (23 tickers)...\nETA: 2 minutes")
        
        try:
            from working_edge_system import WorkingEdgeSystem
            
            system = WorkingEdgeSystem()
            universe = [
                "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
                "GME", "AMC", "PLTR", "COIN", "HOOD", "SPY", "QQQ",
                "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU", "RKLB"
            ]
            
            signals = system.scan(universe, min_score=2)
            self.last_scan_results = signals
            
            # Send summary
            longs = [s for s in signals if s.direction == "LONG"]
            shorts = [s for s in signals if s.direction == "SHORT"]
            avoids = [s for s in signals if s.direction == "AVOID"]
            
            summary = f"""✅ <b>Quick Scan Complete</b>

Scanned: {len(universe)} tickers
Signals: {len(signals)}

🚀 LONG: {len(longs)}
🔻 SHORT: {len(shorts)}
⚠️ AVOID: {len(avoids)}

Use /longs or /shorts for details."""
            
            self.send_message(chat_id, summary)
            
            # Send top longs
            if longs:
                self.send_message(chat_id, "🎯 <b>Top LONG Picks:</b>")
                for s in longs[:3]:
                    text = f"{s.ticker}: +{s.score} ({s.confidence})\n{s.catalyst[:60]}"
                    self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            self.send_message(chat_id, f"❌ Scan failed: {str(e)[:100]}")
    
    def cmd_full(self, chat_id: str):
        """Run full scan."""
        self.send_message(chat_id, "⏳ Running full scan (154 tickers)...\nETA: 7 minutes")
        
        try:
            from market_wide_scanner import MarketWideScanner, get_priority_universe
            
            scanner = MarketWideScanner(delay=0.3)
            universe = get_priority_universe()
            
            signals = scanner.scan(universe, min_score=2)
            self.last_scan_results = signals
            
            # Format results
            longs = [s for s in signals if s.get("direction") == "LONG"]
            
            summary = f"""✅ <b>Full Scan Complete</b>

Scanned: {len(universe)} tickers
Signals: {len(signals)}
🚀 LONG: {len(longs)}

Use /longs for top picks."""
            
            self.send_message(chat_id, summary)
            
            # Send top 5 longs
            if longs:
                self.send_message(chat_id, "🎯 <b>Top 5 LONG Signals:</b>")
                for s in longs[:5]:
                    text = f"<b>{s['ticker']}</b>: +{s['score']}\n{s.get('catalyst', 'N/A')[:50]}"
                    self.send_message(chat_id, text)
            
        except Exception as e:
            logger.error(f"Full scan failed: {e}")
            self.send_message(chat_id, f"❌ Scan failed: {str(e)[:100]}")
    
    def cmd_all(self, chat_id: str):
        """Run complete scan."""
        self.send_message(chat_id, "⏳ Running complete scan (362 tickers)...\nETA: 15 minutes\n\nI'll message you when done.")
        
        # Run in background thread so bot stays responsive
        def run_complete_scan():
            try:
                from market_wide_scanner import MarketWideScanner, get_full_universe
                
                scanner = MarketWideScanner(delay=0.3)
                universe = get_full_universe()
                
                signals = scanner.scan(universe[:200], min_score=2)  # Limit to 200 for speed
                self.last_scan_results = signals
                
                longs = [s for s in signals if s.get("direction") == "LONG"]
                
                self.send_message(chat_id, f"✅ <b>Complete Scan Done!</b>\n\nScanned: 200 tickers\n🚀 LONG signals: {len(longs)}\n\nUse /longs to see picks.")
                
            except Exception as e:
                self.send_message(chat_id, f"❌ Complete scan failed: {str(e)[:100]}")
        
        thread = threading.Thread(target=run_complete_scan)
        thread.daemon = True
        thread.start()
    
    def cmd_longs(self, chat_id: str):
        """Show top long signals."""
        if not self.last_scan_results:
            self.send_message(chat_id, "No scan results yet. Run /quick or /full first.")
            return
        
        longs = [s for s in self.last_scan_results if getattr(s, 'direction', s.get('direction')) == "LONG"]
        
        if not longs:
            self.send_message(chat_id, "No LONG signals found in last scan.")
            return
        
        self.send_message(chat_id, f"🚀 <b>Top {min(5, len(longs))} LONG Signals:</b>")
        
        for s in longs[:5]:
            ticker = getattr(s, 'ticker', s.get('ticker'))
            score = getattr(s, 'score', s.get('score'))
            catalyst = getattr(s, 'catalyst', s.get('catalyst', 'N/A'))
            
            text = f"<b>{ticker}</b> | Score: +{score}\n{catalyst[:80]}"
            self.send_message(chat_id, text)
    
    def cmd_shorts(self, chat_id: str):
        """Show top short signals."""
        if not self.last_scan_results:
            self.send_message(chat_id, "No scan results yet. Run /quick or /full first.")
            return
        
        shorts = [s for s in self.last_scan_results if getattr(s, 'direction', s.get('direction')) == "SHORT"]
        
        if not shorts:
            self.send_message(chat_id, "No SHORT signals found in last scan.")
            return
        
        self.send_message(chat_id, f"🔻 <b>SHORT Signals:</b>")
        
        for s in shorts[:3]:
            ticker = getattr(s, 'ticker', s.get('ticker'))
            score = getattr(s, 'score', s.get('score'))
            text = f"<b>{ticker}</b> | Score: {score}"
            self.send_message(chat_id, text)
    
    def cmd_status(self, chat_id: str):
        """Show bot status."""
        from working_edge_system import WorkingEdgeSystem
        
        system = WorkingEdgeSystem()
        modules = list(system.modules.keys())
        
        status = f"""📊 <b>Bot Status</b>

✅ Online
Modules loaded: {len(modules)}
Last scan: {len(self.last_scan_results)} signals

<b>Available modules:</b>
{', '.join(modules)}

Send /quick or /full to run a scan."""
        
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
