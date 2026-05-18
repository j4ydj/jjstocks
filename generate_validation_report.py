#!/usr/bin/env python3
"""Build ACTIONABLE_VALIDATION.md — one file to verify the whole system."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ACTIONABLE_VALIDATION.md"


def _run_tests() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "test_system.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    lines = [
        ln for ln in (proc.stdout + proc.stderr).splitlines()
        if ln.startswith("=") or ln.startswith("[") or "ALL CHECKS" in ln or "FAILED" in ln
    ]
    return proc.returncode, "\n".join(lines)


def _setup_table(setups) -> str:
    if not setups:
        return "_No setups passed filters on this scan._\n"
    rows = [
        "| Type | Dir | Ticker | Leader | Leader 1d | Focus 1d | r | Lag | OOS hit | n | Entry | Stop | Target |",
        "|------|-----|--------|--------|-----------|----------|---|-----|---------|---|-------|------|--------|",
    ]
    for s in setups:
        oos = f"{s.hit_rate_oos:.0f}%" if s.hit_rate_oos is not None else "—"
        rows.append(
            f"| {s.setup_type} | {s.direction} | {s.ticker} | {s.leader} | "
            f"{s.leader_move_1d:+.1f}% | {s.focus_move_1d:+.1f}% | {s.corr:+.2f} | "
            f"{s.lag_days:+d} | {oos} | {s.hit_n_oos} | "
            f"${s.entry_price:.2f} | ${s.stop_loss:.2f} | ${s.target_price:.2f} |"
        )
    return "\n".join(rows) + "\n"


def _links_table(chain, max_rows: int = 8) -> str:
    f = chain.focus
    rows = [
        f"**{f.ticker}** ${f.last_price:.2f} · 1d {f.return_1d_pct:+.1f}% · 5d {f.return_5d_pct:+.1f}%",
        "",
        "| Node | Layer | r | p | lag | 1d% | OOS hit | n | regime |",
        "|------|-------|---|---|-----|-----|---------|---|--------|",
    ]
    links = sorted(chain.links, key=lambda x: abs(x.corr_21d), reverse=True)[:max_rows]
    for l in links:
        oos = f"{l.lag_hit_rate_oos:.0f}%" if l.lag_hit_rate_oos is not None else "—"
        rows.append(
            f"| {l.node} | {l.layer} | {l.corr_21d:+.3f} | {l.corr_pvalue:.4f} | "
            f"{l.lead_lag_days:+d} | {l.move_1d_pct:+.1f}% | {oos} | {l.lag_hit_n_oos} | "
            f"{'⚠' if l.regime_break else 'ok'} |"
        )
    return "\n".join(rows) + "\n\n"


def build() -> int:
    from chain_ping import (
        ALERT_MODE,
        chains_with_moves,
        format_actionable_ping,
        format_plain_ping,
        format_telegram_ping,
        run_scan,
    )
    from chain_setups import find_all_setups
    from momentum_chain import CORR_LOOKBACK_DAYS, MIN_CORR_ABS

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("Running test_system.py...")
    test_code, test_log = _run_tests()

    print("Running live scan...")
    result = run_scan()
    movers = chains_with_moves(result)
    setups = find_all_setups(movers, result.price_cache)

    map_msg = format_telegram_ping(result)
    act_msg = format_actionable_ping(result, setups) if setups else ""
    plain_act = format_plain_ping(result, act_msg) if act_msg else "(none — Telegram skipped in actionable mode)"

    # Recent log lines
    setup_log = ROOT / "data" / "trade_setups.jsonl"
    recent_logs = []
    if setup_log.exists():
        for line in setup_log.read_text().strip().splitlines()[-5:]:
            try:
                recent_logs.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    backtest_exists = (ROOT / "BACKTEST_LEAD_LAG.md").exists()
    csv_exists = (ROOT / "data" / "BACKTEST_LEAD_LAG.csv").exists()

    md = f"""# Actionable system — validation report

> Generated: **{ts}**  
> Command: `python generate_validation_report.py`

Use this file to verify scans, filters, setups, and test output match what the code actually produced.

---

## 1. Automated tests

Exit code: **{test_code}** ({'PASSED' if test_code == 0 else 'FAILED'})

```
{test_log}
```

---

## 2. Scan snapshot

| Item | Value |
|------|-------|
| Scan time | `{result.scan_time}` |
| Universe | {result.universe_size} tickers |
| Volatility chains | {len(result.chains)} |
| Movers (≥ move threshold) | {len(movers)} |
| **Actionable setups** | **{len(setups)}** |
| Alert mode | `{ALERT_MODE}` |
| Corr window | {CORR_LOOKBACK_DAYS} days |
| Min \\|r\\| | {MIN_CORR_ABS} |
| OOS hit floor | {os.getenv('MIN_OOS_HIT', '55')}% |
| Leader move min | {os.getenv('LEADER_MOVE_MIN', '2')}% |

### Movers today

| Ticker | Price | 1d % | 5d % |
|--------|-------|------|------|
"""
    for c in movers:
        f = c.focus
        md += f"| {f.ticker} | ${f.last_price:.2f} | {f.return_1d_pct:+.1f}% | {f.return_5d_pct:+.1f}% |\n"

    md += f"""
---

## 3. Actionable setups (what Telegram would send)

{ _setup_table(setups) }

### Thesis lines (copy-check)

"""
    for i, s in enumerate(setups, 1):
        md += f"{i}. **{s.direction} {s.ticker}** ({s.setup_type}) — {s.thesis}\n"

    md += f"""
### Plain-text Telegram body (actionable)

```
{plain_act}
```

---

## 4. Relationship map (full mode reference)

`ALERT_MODE=full` would send this ({len(map_msg)} chars):

```
{format_plain_ping(result, map_msg)[:4000]}{'…' if len(map_msg) > 4000 else ''}
```

---

## 5. Top links per mover (verify r, OOS, lag)

"""
    for chain in movers[:5]:
        md += _links_table(chain)

    md += f"""---

## 6. Setup filter checklist (manual spot-check)

For each setup above, confirm:

- [ ] \\|r\\| ≥ {MIN_CORR_ABS}
- [ ] OOS hit ≥ {os.getenv('MIN_OOS_HIT', '55')}% and n ≥ {os.getenv('MIN_HIT_EVENTS', '8')}
- [ ] Leader \\|1d move\\| ≥ {os.getenv('LEADER_MOVE_MIN', '2')}% (catch-up) OR opposite moves (divergence)
- [ ] No `regime_break` on the link used
- [ ] LONG blocked if VIX > {os.getenv('VIX_SPIKE_MAX', '5')}% and SPY & QQQ both < -{os.getenv('MACRO_DOWN_BLOCK', '1')}%

---

## 7. Historical backtest files

| File | Present |
|------|---------|
| `BACKTEST_LEAD_LAG.md` | {'yes' if backtest_exists else 'no — run `python lead_lag_backtest.py`'} |
| `data/BACKTEST_LEAD_LAG.csv` | {'yes' if csv_exists else 'no'} |

---

## 8. Recent setup log (`data/trade_setups.jsonl`)

"""
    if recent_logs:
        md += "```json\n"
        for rec in recent_logs:
            md += json.dumps(rec, indent=2) + "\n"
        md += "```\n"
    else:
        md += "_No log file yet — run `python chain_ping.py` once._\n"

    md += """
---

## 9. Reproduce everything

```bash
cd /Users/home/stocks
python test_system.py
python generate_validation_report.py   # refreshes this file
python chain_ping.py                 # dry-run Telegram body
python lead_lag_backtest.py          # full 419-pair CSV
python signal_log.py                 # fill 1d/5d outcomes on past setups
```

**Telegram live test** (sends real message if env set):

```bash
set -a && source .telegram_config && set +a
python -c "from chain_ping import scan_and_notify; scan_and_notify(send_telegram=True)"
```

---

*End of validation report.*
"""
    OUT.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT} ({len(setups)} setups, test exit {test_code})")
    return test_code


if __name__ == "__main__":
    sys.exit(build())
