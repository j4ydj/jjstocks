#!/usr/bin/env python3
"""
Telegram remote trigger — single command: /run

Polls getUpdates in a background thread (Railway jjstocks service).
Only TELEGRAM_CHAT_ID may invoke scans.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
RUN_COMMAND = os.getenv("TELEGRAM_RUN_COMMAND", "/run").strip().lower()
POLL_INTERVAL_SEC = float(os.getenv("TELEGRAM_POLL_SEC", "2"))


def _api(method: str, params: Optional[dict] = None) -> Optional[dict]:
    if not TELEGRAM_BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params or {}).encode() if params else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            body = json.loads(resp.read().decode())
            if not body.get("ok"):
                logger.warning("Telegram API %s: %s", method, body)
                return None
            return body.get("result")
    except Exception as e:
        logger.error("Telegram API %s failed: %s", method, e)
        return None


def send_text(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    r = _api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text[:4000],
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        },
    )
    return r is not None


def _authorized(chat_id: str) -> bool:
    if not TELEGRAM_CHAT_ID:
        return False
    return str(chat_id) == str(TELEGRAM_CHAT_ID)


def _run_pipeline(chat_id: str) -> None:
    try:
        from daily_pipeline import run_pipeline, format_plain

        ok, plain = run_pipeline(send_telegram=True)
        tail = (plain or "")[-1500:]
        status = "✅ Scan finished" if ok else "⚠️ Scan finished with errors"
        send_text(chat_id, f"{status}\n\n<pre>{_esc_pre(tail)}</pre>", parse_mode="HTML")
    except Exception as e:
        logger.exception("Pipeline run failed")
        send_text(chat_id, f"❌ Scan failed: {_esc_html(str(e)[:500])}")


def _esc_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_pre(s: str) -> str:
    return _esc_html(s)


def _handle_message(chat_id: str, text: str) -> None:
    cmd = (text or "").strip().lower().split()[0]
    if cmd != RUN_COMMAND:
        if cmd in ("/start", "/help"):
            send_text(
                chat_id,
                "🤖 <b>Stocks pipeline</b>\n\n"
                f"Send <b>{RUN_COMMAND}</b> to run a full scan (movements + trades + tracking).\n"
                "Automatic scan also runs daily ~21:00 UTC.",
            )
        return
    if not _authorized(chat_id):
        send_text(chat_id, "⛔ Unauthorized chat.")
        return
    send_text(chat_id, f"⏳ Running pipeline… (~1–3 min). You will get the full alert when done.")
    threading.Thread(target=_run_pipeline, args=(chat_id,), daemon=True).start()


def _poll_loop() -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram commands disabled (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)")
        return
    offset = 0
    logger.info("Telegram command listener: %s (chat %s)", RUN_COMMAND, TELEGRAM_CHAT_ID)
    while True:
        try:
            updates = _api("getUpdates", {"offset": offset, "timeout": 25}) or []
            for upd in updates:
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = str(chat.get("id", ""))
                text = msg.get("text") or ""
                if chat_id and text:
                    _handle_message(chat_id, text)
        except Exception as e:
            logger.error("Telegram poll error: %s", e)
        import time
        time.sleep(POLL_INTERVAL_SEC)


def start_telegram_command_listener() -> None:
    """Start background polling (idempotent)."""
    if os.getenv("TELEGRAM_COMMANDS", "1") != "1":
        return
    t = threading.Thread(target=_poll_loop, daemon=True, name="telegram-commands")
    t.start()
