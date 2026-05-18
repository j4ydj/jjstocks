#!/usr/bin/env python3
"""
HTTP server for serverless: external cron hits this URL to run the scan.
Set CRON_SECRET in Railway and use the same in cron-job.org.
"""
import os
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))
CRON_SECRET = os.environ.get("CRON_SECRET", "").strip()


class TriggerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        token = (qs.get("token") or [None])[0]

        # Health: no token, always 200 (Railway can ping this)
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true, "status": "up"}')
            return

        if path not in ("/", "/run", "/cron", "/run/outcomes"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        if CRON_SECRET and token != CRON_SECRET:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid or missing token")
            return

        if not CRON_SECRET:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"Set CRON_SECRET in Railway and pass ?token=CRON_SECRET")
            return

        try:
            if path == "/run/outcomes":
                from trade_tracker import update_outcomes, write_report, SETUP_FILE
                n = update_outcomes(min_age_days=1)
                write_report()
                out = {"ok": True, "updated": n, "log": SETUP_FILE}
            else:
                from cloud_run import run_scan
                success = run_scan()
                out = {"ok": success, "message": "OK" if success else "Scan failed"}
        except Exception as e:
            logger.exception("Trigger run failed")
            out = {"ok": False, "message": str(e)}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)


def main():
    server = HTTPServer(("0.0.0.0", PORT), TriggerHandler)
    logger.info("Trigger server listening on 0.0.0.0:%s (hit /run?token=YOUR_CRON_SECRET)", PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
