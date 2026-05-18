# Actionable system — validation report

> Generated: **2026-05-18 11:26:20**  
> Command: `python generate_validation_report.py`

Use this file to verify scans, filters, setups, and test output match what the code actually produced.

---

## 1. Automated tests

Exit code: **0** (PASSED)

```
============================================================
============================================================
[PASS] imports
[PASS] scan — 518 tickers, 8 chains, 5 movers
[PASS] setups — 2 actionable, map 1595 chars
[PASS] telegram — message delivered
[PASS] trigger server — /health 200, bad token 403
============================================================
ALL CHECKS PASSED
```

---

## 2. Scan snapshot

| Item | Value |
|------|-------|
| Scan time | `2026-05-18 11:27:16` |
| Universe | 518 tickers |
| Volatility chains | 8 |
| Movers (≥ move threshold) | 5 |
| **Actionable setups** | **2** |
| Alert mode | `actionable` |
| Corr window | 60 days |
| Min \|r\| | 0.55 |
| OOS hit floor | 55% |
| Leader move min | 2% |

### Movers today

| Ticker | Price | 1d % | 5d % |
|--------|-------|------|------|
| RKLB | $124.77 | -5.9% | +18.3% |
| AKAM | $150.88 | -3.1% | +2.1% |
| JOBY | $10.36 | -2.6% | -4.7% |
| DDOG | $207.98 | +2.5% | +3.9% |
| ZTS | $74.22 | -1.7% | -10.4% |

---

## 3. Actionable setups (what Telegram would send)

| Type | Dir | Ticker | Leader | Leader 1d | Focus 1d | r | Lag | OOS hit | n | Entry | Stop | Target |
|------|-----|--------|--------|-----------|----------|---|-----|---------|---|-------|------|--------|
| catch_up | SHORT | RKLB | LUNR | -7.2% | -5.9% | +0.75 | +0 | 86% | 36 | $124.77 | $133.18 | $107.95 |
| catch_up | SHORT | JOBY | RKLB | -5.9% | -2.6% | +0.59 | +0 | 79% | 38 | $10.36 | $10.88 | $9.32 |


### Thesis lines (copy-check)

1. **SHORT RKLB** (catch_up) — LUNR -7.2% today; RKLB lagging (-5.9%). Historically follows same day (OOS hit 86%, n=36).
2. **SHORT JOBY** (catch_up) — RKLB -5.9% today; JOBY lagging (-2.6%). Historically follows same day (OOS hit 79%, n=38).

### Plain-text Telegram body (actionable)

```
Trade setups
2026-05-18 11:27:16
2 idea(s) · r≥0.55 · OOS hit≥55%

📉 SHORT RKLB  Catch Up
  LUNR -7.2% today; RKLB lagging (-5.9%). Historically follows same day (OOS hit 86%, n=36).
  Leader: LUNR -7.2% · r=+0.75 · OOS hit 86%
  Entry $124.77 · Stop $133.18 · Target $107.95 · Risk 6.7% · R:R 2.0 · Size ~30% port

📉 SHORT JOBY  Catch Up
  RKLB -5.9% today; JOBY lagging (-2.6%). Historically follows same day (OOS hit 79%, n=38).
  Leader: RKLB -5.9% · r=+0.59 · OOS hit 79%
  Entry $10.36 · Stop $10.88 · Target $9.32 · Risk 5.0% · R:R 2.0 · Size ~30% port
```

---

## 4. Relationship map (full mode reference)

`ALERT_MODE=full` would send this (1595 chars):

```
Chain alert
2026-05-18 11:27:16
corr 60d · min |r| 0.55

RKLB  $124.77  -5.9% today  (+18.3% over 5 days)
Linked names (60d r≥0.55):
  • LUNR  $33.89  -7.2% today — r60 +0.75, together; same day; same way today (p&lt;0.05 n=60, OOS 86%)
  • ASTS  $83.67  +0.8% today — r60 +0.71, together; same day; opposite today (p&lt;0.05 n=60, OOS 80%)
  • RDW  $nan  +nan% today — r60 +0.70, together; same day; opposite today (p&lt;0.05 n=60, OOS 76%)
  • BKSY  $nan  +nan% today — r60 +0.70, together; same day; opposite today (p&lt;0.05 n=60, OOS 73%)
  • SPCE  $nan  +nan% today — r60 +0.59, together; same day; opposite today (p&lt;0.05 n=60, OOS 71%)
Market (1 per bucket):
  • XLK  $nan  +nan% today — r60 +0.59, together; same day; opposite today (p&lt;0.05 n=60, OOS 84%)
  • ARKK  $nan  +nan% today — r60 +0.58, together; same day; opposite today (p&lt;0.05 n=60, OOS 93%)

AKAM  $150.88  -3.1% today  (+2.1% over 5 days)

JOBY  $10.36  -2.6% today  (-4.7% over 5 days)
Linked names (60d r≥0.55):
  • RKLB  $124.77  -5.9% today — r60 +0.59, together; same day; same way today (p&lt;0.05 n=60, OOS 79%)
Market (1 per bucket):
  • ARKK  $nan  +nan% today — r60 +0.68, together; same day; opposite today (p&lt;0.05 n=60, OOS 87%)
  • XLK  $nan  +nan% today — r60 +0.57, together; same day; opposite today (p&lt;0.05 n=60, OOS 84%)
  • SPY  $nan  +nan% today — r60 +0.56, together; same day; opposite today (p&lt;0.05 n=60, OOS 91%)

DDOG  $207.98  +2.5% today  (+3.9% over 5 days)
```

---

## 5. Top links per mover (verify r, OOS, lag)

**RKLB** $124.77 · 1d -5.9% · 5d +18.3%

| Node | Layer | r | p | lag | 1d% | OOS hit | n | regime |
|------|-------|---|---|-----|-----|---------|---|--------|
| LUNR | micro | +0.753 | 0.0000 | +0 | -7.2% | 86% | 36 | ok |
| ASTS | micro | +0.710 | 0.0000 | +0 | +0.8% | 80% | 39 | ok |
| RDW | micro | +0.702 | 0.0000 | +0 | +nan% | 76% | 34 | ok |
| BKSY | micro | +0.699 | 0.0000 | +0 | +nan% | 73% | 37 | ok |
| SPCE | micro | +0.591 | 0.0000 | +0 | +nan% | 71% | 31 | ok |
| XLK | macro | +0.586 | 0.0000 | +0 | +nan% | 84% | 25 | ok |
| ARKK | macro | +0.577 | 0.0000 | +0 | +nan% | 93% | 30 | ok |
| PL | micro | +0.552 | 0.0000 | +0 | +nan% | 79% | 34 | ok |

**AKAM** $150.88 · 1d -3.1% · 5d +2.1%

| Node | Layer | r | p | lag | 1d% | OOS hit | n | regime |
|------|-------|---|---|-----|-----|---------|---|--------|

**JOBY** $10.36 · 1d -2.6% · 5d -4.7%

| Node | Layer | r | p | lag | 1d% | OOS hit | n | regime |
|------|-------|---|---|-----|-----|---------|---|--------|
| ARKK | macro | +0.675 | 0.0000 | +0 | +nan% | 87% | 30 | ok |
| RKLB | micro | +0.593 | 0.0000 | +0 | -5.9% | 79% | 38 | ok |
| QQQ | macro | +0.584 | 0.0000 | +0 | +nan% | 90% | 19 | ok |
| XLK | macro | +0.574 | 0.0000 | +0 | +nan% | 84% | 25 | ok |
| SPY | macro | +0.561 | 0.0000 | +0 | +nan% | 91% | 11 | ok |

**DDOG** $207.98 · 1d +2.5% · 5d +3.9%

| Node | Layer | r | p | lag | 1d% | OOS hit | n | regime |
|------|-------|---|---|-----|-----|---------|---|--------|

**ZTS** $74.22 · 1d -1.7% · 5d -10.4%

| Node | Layer | r | p | lag | 1d% | OOS hit | n | regime |
|------|-------|---|---|-----|-----|---------|---|--------|

---

## 6. Setup filter checklist (manual spot-check)

For each setup above, confirm:

- [ ] \|r\| ≥ 0.55
- [ ] OOS hit ≥ 55% and n ≥ 8
- [ ] Leader \|1d move\| ≥ 2% (catch-up) OR opposite moves (divergence)
- [ ] No `regime_break` on the link used
- [ ] LONG blocked if VIX > 5% and SPY & QQQ both < -1%

---

## 7. Historical backtest files

| File | Present |
|------|---------|
| `BACKTEST_LEAD_LAG.md` | yes |
| `data/BACKTEST_LEAD_LAG.csv` | yes |

---

## 8. Recent setup log (`data/trade_setups.jsonl`)

```json
{
  "logged_at": "2026-05-18T11:22:32.972890",
  "scan_time": "2026-05-18 11:22:32",
  "setup_type": "catch_up",
  "ticker": "RKLB",
  "direction": "SHORT",
  "leader": "LUNR",
  "thesis": "LUNR -7.2% today; RKLB lagging (-5.9%). Historically follows same day (OOS hit 86%, n=36).",
  "leader_move_1d": -7.2,
  "focus_move_1d": -5.87,
  "corr": 0.753,
  "lag_days": 0,
  "hit_rate": 83.0,
  "hit_rate_oos": 86.1,
  "hit_n_oos": 36,
  "entry_price": 124.77,
  "stop_loss": 133.18,
  "target_price": 107.95,
  "risk_pct": 6.7,
  "risk_reward": 2.0,
  "position_pct": 29.7,
  "outcomes": {}
}
{
  "logged_at": "2026-05-18T11:22:32.973420",
  "scan_time": "2026-05-18 11:22:32",
  "setup_type": "catch_up",
  "ticker": "JOBY",
  "direction": "SHORT",
  "leader": "RKLB",
  "thesis": "RKLB -5.9% today; JOBY lagging (-2.6%). Historically follows same day (OOS hit 79%, n=38).",
  "leader_move_1d": -5.87,
  "focus_move_1d": -2.63,
  "corr": 0.593,
  "lag_days": 0,
  "hit_rate": 84.9,
  "hit_rate_oos": 78.9,
  "hit_n_oos": 38,
  "entry_price": 10.36,
  "stop_loss": 10.88,
  "target_price": 9.32,
  "risk_pct": 5.0,
  "risk_reward": 2.0,
  "position_pct": 30.0,
  "outcomes": {}
}
{
  "logged_at": "2026-05-18T11:22:32.973680",
  "scan_time": "2026-05-18 11:22:32",
  "setup_type": "catch_up",
  "ticker": "RKLB",
  "direction": "SHORT",
  "leader": "RDW",
  "thesis": "RDW +nan% today; RKLB lagging (-5.9%). Historically follows same day (OOS hit 76%, n=34).",
  "leader_move_1d": NaN,
  "focus_move_1d": -5.87,
  "corr": 0.702,
  "lag_days": 0,
  "hit_rate": 78.4,
  "hit_rate_oos": 76.5,
  "hit_n_oos": 34,
  "entry_price": 124.77,
  "stop_loss": 133.18,
  "target_price": 107.95,
  "risk_pct": 6.7,
  "risk_reward": 2.0,
  "position_pct": 29.7,
  "outcomes": {}
}
{
  "logged_at": "2026-05-18T11:23:15.373326",
  "scan_time": "2026-05-18 11:23:15",
  "setup_type": "catch_up",
  "ticker": "RKLB",
  "direction": "SHORT",
  "leader": "LUNR",
  "thesis": "LUNR -7.2% today; RKLB lagging (-5.9%). Historically follows same day (OOS hit 86%, n=36).",
  "leader_move_1d": -7.2,
  "focus_move_1d": -5.87,
  "corr": 0.753,
  "lag_days": 0,
  "hit_rate": 83.0,
  "hit_rate_oos": 86.1,
  "hit_n_oos": 36,
  "entry_price": 124.77,
  "stop_loss": 133.18,
  "target_price": 107.95,
  "risk_pct": 6.7,
  "risk_reward": 2.0,
  "position_pct": 29.7,
  "outcomes": {}
}
{
  "logged_at": "2026-05-18T11:23:15.373829",
  "scan_time": "2026-05-18 11:23:15",
  "setup_type": "catch_up",
  "ticker": "JOBY",
  "direction": "SHORT",
  "leader": "RKLB",
  "thesis": "RKLB -5.9% today; JOBY lagging (-2.6%). Historically follows same day (OOS hit 79%, n=38).",
  "leader_move_1d": -5.87,
  "focus_move_1d": -2.63,
  "corr": 0.593,
  "lag_days": 0,
  "hit_rate": 84.9,
  "hit_rate_oos": 78.9,
  "hit_n_oos": 38,
  "entry_price": 10.36,
  "stop_loss": 10.88,
  "target_price": 9.32,
  "risk_pct": 5.0,
  "risk_reward": 2.0,
  "position_pct": 30.0,
  "outcomes": {}
}
```

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
