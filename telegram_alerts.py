#!/usr/bin/env python3
"""
TELEGRAM ALERTS v2 - Trade Alerts Only
=======================================
Sends actionable trade alerts. No noise.

Each message is a complete trade:
  - Entry price
  - Stop loss
  - Target price
  - Risk/reward ratio
  - Position size
  - Exit date
  - Confirmation signals
"""
import os
import logging
from datetime import datetime
from typing import List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class TelegramBot:

    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            logger.warning("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

    def send_message(self, text: str) -> bool:
        if not self.enabled:
            logger.info(f"[DRY RUN] {text[:80]}...")
            return True
        try:
            import urllib.request
            import urllib.parse
            data = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }).encode()
            req = urllib.request.Request(
                f"{self.base_url}/sendMessage", data=data, method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_trade(self, trade) -> bool:
        """Send a single actionable trade alert."""
        if trade.direction == "BUY":
            emoji = "📈"
            dir_text = "BUY"
        else:
            emoji = "📉"
            dir_text = "SHORT"

        checks = " ".join(f"[{s}]" for s in trade.signals)

        slippage = getattr(trade, "slippage_pct", 1.0)
        lines = [
            f"{emoji} <b>{dir_text} {trade.ticker}</b> @ <b>${trade.entry_price}</b>",
            "",
            f"Stop: ${trade.stop_loss} (-{trade.risk_pct}%)",
            f"Target: ${trade.target_price} (+{trade.reward_pct}%)",
            f"R:R <b>{trade.risk_reward}:1</b>",
            f"Position: {trade.position_pct}% of portfolio",
            f"Exit by: {trade.exit_date}",
            "",
            f"<b>Gap rule:</b> If open is &gt;{slippage}% from entry, cancel or recalc size.",
            "",
            f"<b>{trade.conviction}/5</b> signals: {checks}",
        ]
        for reason in trade.reasons:
            # Escape HTML special characters in reason text
            safe = reason.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"  - {safe}")
        lines.append("")
        lines.append(f"<i>{trade.signal_date} {trade.scan_time}</i>")

        text = "\n".join(lines)

        return self.send_message(text)

    def send_scan_summary(self, trades: list, universe_size: int) -> bool:
        """Send scan summary - only if there are trades."""
        buys = [t for t in trades if t.direction == "BUY"]
        shorts = [t for t in trades if t.direction == "SHORT"]

        if not trades:
            text = f"""📊 <b>Scan Complete</b> - No trades today

Scanned: {universe_size} tickers
Trades: 0

No setups met the 3-signal minimum.
This is normal - selectivity is the edge.

<i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"""
        else:
            text = f"""📊 <b>Scan Complete</b> - {len(trades)} trade(s) found

Scanned: {universe_size} tickers
📈 BUY: {len(buys)}
📉 SHORT: {len(shorts)}

<i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"""

        return self.send_message(text)


if __name__ == "__main__":
    bot = TelegramBot()
    bot.send_message("🧪 <b>Test</b> - Bot is alive")
