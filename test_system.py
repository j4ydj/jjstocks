#!/usr/bin/env python3
"""Run `python test_system.py` for a quick proof the pipeline works."""
import sys
import urllib.request
import json
import os


def main():
    failed = []
    print("=" * 60)
    print("  SYSTEM PROOF TESTS")
    print("=" * 60)

    # 1 Imports
    try:
        from chain_ping import run_scan, format_telegram_ping, chains_with_moves
        from cloud_run import run_scan as _unused
        print("[PASS] imports")
    except Exception as e:
        print("[FAIL] imports:", e)
        failed.append("imports")
        return 1

    # 2 Scan
    try:
        r = run_scan()
        assert len(r.chains) >= 1 and r.universe_size > 100
        movers = chains_with_moves(r)
        print(f"[PASS] scan — {r.universe_size} tickers, {len(r.chains)} chains, {len(movers)} movers")
    except Exception as e:
        print("[FAIL] scan:", e)
        failed.append("scan")
        return 1

    # 3 Message content
    try:
        msg = format_telegram_ping(r)
        assert "Chain alert" in msg and r.scan_time in msg
        assert "$" in msg and "%" in msg
        assert "r60" in msg or "corr" in msg
        assert "leads" in msg or "lags" in msg or "same day" in msg or "fwd" in msg
        assert all(c.focus.last_price > 0 for c in r.chains)
        # At least one chain link should carry lead/lag from momentum_chain
        has_lag = any(l.lead_lag_days != 0 for c in r.chains for l in c.links)
        print(
            f"[PASS] message — {len(msg)} chars, timestamp + prices + "
            f"timing ({'lead/lag in data' if has_lag else 'same-day only'})"
        )
    except Exception as e:
        print("[FAIL] message:", e)
        failed.append("message")
        return 1

    # 4 Telegram (optional if env set)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            with urllib.request.urlopen(url, timeout=10) as resp:
                me = json.loads(resp.read())
            if not me.get("ok"):
                raise RuntimeError("getMe failed")
            from telegram_alerts import TelegramBot
            bot = TelegramBot()
            if bot.send_message(f"✅ <b>test_system.py passed</b>\n<i>{r.scan_time}</i>\n\n{msg[:3000]}"):
                print("[PASS] telegram — message delivered")
            else:
                print("[FAIL] telegram send_message returned false")
                failed.append("telegram")
        except Exception as e:
            print("[FAIL] telegram:", e)
            failed.append("telegram")
    else:
        print("[SKIP] telegram — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

    # 5 Trigger auth (local)
    try:
        import trigger_server
        import threading
        from http.server import HTTPServer

        trigger_server.CRON_SECRET = "proof-secret"
        port = 18766
        trigger_server.PORT = port
        srv = HTTPServer(("127.0.0.1", port), trigger_server.TriggerHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        import time
        time.sleep(0.2)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as h:
            assert h.status == 200
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/run?token=bad", timeout=2)
            print("[FAIL] trigger should 403 bad token")
            failed.append("trigger")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        srv.shutdown()
        print("[PASS] trigger server — /health 200, bad token 403")
    except Exception as e:
        print("[FAIL] trigger:", e)
        failed.append("trigger")

    print("=" * 60)
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
