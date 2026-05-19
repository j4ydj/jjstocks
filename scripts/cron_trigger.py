#!/usr/bin/env python3
"""Railway cron entry: HTTP trigger daily scan + outcomes, then exit."""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv(
    "RAILWAY_SERVICE_JJSTOCKS_URL",
    os.getenv("RAILWAY_PUBLIC_DOMAIN", "jjstocks-production.up.railway.app"),
).rstrip("/")
if not BASE.startswith("http"):
    BASE = f"https://{BASE}"

SECRET = os.getenv("CRON_SECRET", "").strip()
TIMEOUT = int(os.getenv("CRON_HTTP_TIMEOUT", "600"))


def _get(path: str) -> str:
    if not SECRET:
        print("CRON_SECRET not set", file=sys.stderr)
        sys.exit(1)
    url = f"{BASE}{path}?token={SECRET}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    print(f"Trigger scan at {BASE}/run ...")
    try:
        body = _get("/run")
        print(body[:2000])
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    print(f"Trigger outcomes at {BASE}/run/outcomes ...")
    try:
        print(_get("/run/outcomes")[:1000])
    except Exception as e:
        print(f"Outcomes warning: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
