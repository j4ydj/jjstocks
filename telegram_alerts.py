#!/usr/bin/env python3
"""
Telegram delivery for chain alerts (see chain_ping.py for message text).
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

    def send_momentum_scan(self, result) -> bool:
        """Send momentum chain scan: top volatile + per-name upstream/downstream."""
        picks = result.top_volatile
        lines = [
            "🔗 <b>Momentum Chain Scan</b>",
            f"Universe {result.universe_size} → focus top {len(picks)} volatile",
            "",
            "<b>Top volatile now</b>",
        ]
        for p in picks:
            lines.append(
                f"#{p.rank} <b>{p.ticker}</b> vol {p.vol_annualized_pct:.0f}% "
                f"5d {p.return_5d_pct:+.1f}% 1d {p.return_1d_pct:+.1f}%"
            )

        self.send_message("\n".join(lines))

        for chain in result.chains[:5]:
            f = chain.focus
            msg = [f"⚡ <b>{f.ticker}</b> (#{f.rank} vol {f.vol_annualized_pct:.0f}%)"]
            for n in chain.narrative[:2]:
                safe = n.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                msg.append(f"• {safe}")
            up = [l for l in chain.links if l.direction == "upstream"][:4]
            if up:
                msg.append("\n<b>Upstream</b>")
                for l in up:
                    msg.append(
                        f"  {l.node} corr{l.corr_21d:+.2f} lag{l.lead_lag_days:+d}d "
                        f"1d{l.move_1d_pct:+.1f}%"
                    )
            down = [l for l in chain.links if l.direction == "downstream"][:3]
            if down:
                msg.append("\n<b>Downstream</b>")
                for l in down:
                    msg.append(f"  {l.node} corr{l.corr_21d:+.2f}")
            recent = chain.events[-5:]
            if recent:
                msg.append("\n<b>Recent chain</b>")
                for e in recent:
                    arrow = "↑" if e.direction == "up" else "↓"
                    msg.append(f"  {e.date} {e.node} {arrow}{abs(e.move_pct):.1f}%")
            self.send_message("\n".join(msg))

        if len(result.chains) > 5:
            self.send_message(
                f"<i>+{len(result.chains) - 5} more chains in JSON snapshot</i>"
            )
        return True

    def send_trade_play(self, play) -> bool:
        """Send a momentum-chain trade play."""
        emoji = "📈" if play.direction == "BUY" else "📉"
        lines = [
            f"{emoji} <b>{play.direction} {play.ticker}</b> — <i>{play.play_type}</i>",
            f"@ ${play.entry_price}  Stop ${play.stop_loss} ({play.risk_pct}%)",
            f"Target ${play.target_price} (+{play.reward_pct}%)  R:R {play.risk_reward}",
            f"Size {play.position_pct}%  Exit {play.exit_date}",
            f"<b>Score {getattr(play, 'score', 0)}/100</b>  Conviction {play.conviction}/5",
            "",
            f"<b>Trigger:</b> {play.trigger}",
        ]
        if getattr(play, "trigger_price", None):
            lines.append(f"<b>Level:</b> ${play.trigger_price}")
        lines.extend([
            f"<b>Invalidate:</b> {play.invalidation}",
            f"<b>Watch:</b> {', '.join(play.watchlist)}",
        ])
        if play.related_ticker:
            lines.append(f"<b>Related:</b> {play.related_ticker}")
        if getattr(play, "basket_tickers", None):
            lines.append(f"<b>Basket:</b> {', '.join(play.basket_tickers)}")
        for t in play.thesis[:4]:
            safe = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"• {safe}")
        return self.send_message("\n".join(lines))


if __name__ == "__main__":
    bot = TelegramBot()
    bot.send_message("🧪 <b>Test</b> - Bot is alive")
