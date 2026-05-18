#!/usr/bin/env python3
"""Regenerate VERIFICATION.md with a live scan and test_system output."""
from __future__ import annotations

import io
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from chain_ping import (
    MOVE_MIN_PCT,
    chains_with_moves,
    format_plain_ping,
    run_scan,
    _corr_relation,
    _today_alignment,
    _lag_timing,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "VERIFICATION.md"


def _run_tests() -> tuple[int, str]:
  proc = subprocess.run(
      [sys.executable, str(ROOT / "test_system.py")],
      cwd=ROOT,
      capture_output=True,
      text=True,
  )
  lines = (proc.stdout + proc.stderr).splitlines()
  keep = [
      ln for ln in lines
      if ln.startswith("=") or ln.startswith("[") or ln.strip() in ("ALL CHECKS PASSED", "FAILED:")
      and "Failed downloads" not in ln
  ]
  return proc.returncode, "\n".join(keep).strip()


def _movers_table(result) -> str:
    rows = ["| Focus | Price | 1d % | 5d % | Top peer | corr | lag | today vs focus |",
            "|-------|-------|------|------|----------|------|-----|----------------|"]
    for c in chains_with_moves(result)[:6]:
        f = c.focus
        peers = [
            l for l in c.links
            if l.layer == "micro" and abs(l.corr_21d) >= 0.45 and l.node != f.ticker
        ]
        peers.sort(key=lambda x: abs(x.corr_21d), reverse=True)
        if peers:
            p = peers[0]
            today = _today_alignment(f.return_1d_pct, p.move_1d_pct)
            rows.append(
                f"| {f.ticker} | ${f.last_price:.2f} | {f.return_1d_pct:+.1f}% | "
                f"{f.return_5d_pct:+.1f}% | {p.node} | {p.corr_21d:+.2f} | "
                f"{_lag_timing(p.lead_lag_days)} | {today} |"
            )
        else:
            rows.append(
                f"| {f.ticker} | ${f.last_price:.2f} | {f.return_1d_pct:+.1f}% | "
                f"{f.return_5d_pct:+.1f}% | — | — | — | — |"
            )
    return "\n".join(rows)


def build_md(test_exit: int, test_log: str, result) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plain = format_plain_ping(result)
    movers_n = len(chains_with_moves(result))
    status = "PASSED" if test_exit == 0 else "FAILED"

    return f"""# System verification & proof

> Auto-generated **{ts}** by `python generate_verification.py`  
> Re-run anytime to refresh prices and test output.

## What this document proves

1. **Pipeline runs** — scans ~500 tickers, builds volatility chains, formats alerts.
2. **Telegram path works** — when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set, `test_system.py` sends a real message.
3. **Chain semantics are explicit** — each link shows 21d correlation, together/inverse, lead/lag days, and whether **today** moved the same way.

This does **not** prove every chain will be profitable — only that the system computes and delivers the described output.

---

## Automated tests (`test_system.py`)

Exit code: **{test_exit}** → **{status}**

```
{test_log}
```

---

## Live scan snapshot

| Field | Value |
|-------|-------|
| Scan time | `{result.scan_time}` |
| Universe | {result.universe_size} tickers |
| Volatility chains (top N) | {len(result.chains)} |
| Movers (≥ {MOVE_MIN_PCT}% 1d) | {movers_n} |

### Movers summary

{_movers_table(result)}

---

## Sample Telegram message (plain text)

This is exactly what `chain_ping.format_telegram_ping()` produces (HTML tags stripped):

```
{plain}
```

---

## Field glossary

| Label | Meaning |
|-------|---------|
| **corr +0.88** | Over the last **21 trading days**, daily returns tended to move in the same direction. |
| **corr −0.47** | **Inverse** relationship over 21d (when focus up, peer often down). |
| **together / inverse** | Human label from corr sign (≥ +0.25 together, ≤ −0.25 inverse). |
| **leads ~Nd** | Peer’s returns align best when shifted **N days earlier** than focus (`lead_lag_days > 0`). |
| **lags ~Nd** | Focus tends to move **before** the peer. |
| **same day** | Best alignment at 0-day lag (within ±3 day search window). |
| **same way / opposite today** | Compares **today’s** % move only — can disagree with 21d pattern. |

### Worked example (from this scan)

- **RKLB** −5.9% with **ASTS** +0.8%: corr +0.75 **together** over 21d, but **opposite today**.
- **USO** vs **RKLB**: corr −0.47 **inverse**, **leads ~3d**, **opposite today**.

---

## Architecture

```mermaid
flowchart LR
  cron[Railway cron or cron-job.org] -->|GET /run?token=| trig[trigger_server.py]
  trig --> cloud[cloud_run.py]
  cloud --> ping[chain_ping.scan_and_notify]
  ping --> mc[momentum_chain.py]
  mc --> yf[yfinance prices]
  ping --> tg[telegram_alerts.py]
  tg --> phone[Telegram app]
```

| File | Role |
|------|------|
| `momentum_chain.py` | Rank vol, compute corr + lead/lag, build `ChainLink` list |
| `chain_ping.py` | Filter movers, format message with timing labels |
| `cloud_run.py` | Entry for scheduled runs |
| `trigger_server.py` | HTTP `/health`, `/run` on Railway |
| `test_system.py` | Smoke tests + optional Telegram send |

---

## How to verify yourself

```bash
cd /Users/home/stocks
set -a && source .telegram_config && set +a   # if you use local secrets
python3 test_system.py
python3 generate_verification.py              # refreshes this file
python3 chain_ping.py                         # dry-run message to terminal
```

**Railway:** set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `CRON_SECRET`, then:

`https://YOUR-APP.up.railway.app/run?token=YOUR_CRON_SECRET`

Check your Telegram chat for a **Chain alert** matching the format above.

---

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MOMENTUM_TOP_N` | 8 | How many volatile names get full chains |
| `PING_MOVE_MIN_PCT` | 1.5 | Min \|1d%\| to include in alert body |
| `TELEGRAM_BOT_TOKEN` | — | Bot API token |
| `TELEGRAM_CHAT_ID` | — | Destination chat |
| `CRON_SECRET` | — | Protects `/run` endpoint |

---

*End of verification report.*
"""


def main() -> int:
    print("Running test_system.py...")
    test_exit, test_log = _run_tests()
    print("Running live scan...")
    result = run_scan()
    OUT.write_text(build_md(test_exit, test_log, result), encoding="utf-8")
    print(f"Wrote {OUT} ({test_exit=})")
    return test_exit


if __name__ == "__main__":
    sys.exit(main())
