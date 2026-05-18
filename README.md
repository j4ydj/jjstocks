# Momentum Chain Alerts

Finds the most volatile stocks, then tells you on Telegram: **what moved**, at **what price**, and **what usually moves with it** — timestamped.

## Railway (automatic)

1. Deploy this repo on Railway (`python trigger_server.py` — already in `railway.json`).
2. Set variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `CRON_SECRET` (random string)
3. Point [cron-job.org](https://cron-job.org) at:
   ```text
   https://YOUR-APP.up.railway.app/run?token=YOUR_CRON_SECRET
   ```
   Schedule: hourly on weekdays, **5 minute timeout**.

See `RAILWAY_CRON.md` for details.

**Persist trade history on Railway:** mount a volume at `/data` and set `DATA_DIR=/data` (see `RAILWAY_CRON.md`).

## Trade tracking

Every proposed trade is logged to `data/trade_setups.jsonl` with entry, stop, target, and forward outcomes.

```bash
python trade_tracker.py --report   # TRACKING_REPORT.md + data/trade_tracker.csv
python trade_tracker.py --fill      # refresh 1d/5d/10d returns + stop/target hits
```

Default mode is **actionable** — Telegram only when a setup passes filters (`ALERT_MODE=actionable`). All setups are still logged even on quiet scans.

## Example Telegram message

```text
Chain alert
2026-05-17 22:30:00

RKLB  $124.77  -5.9% today  (+18.3% over 5 days)
These often move with it:
  • LUNR  $8.42  -7.2% today
  • ASTS  $28.15  +0.8% today
Macro to watch (moved first):
  • QQQ  $512.30  -1.5% today
```

## Run locally

```bash
python chain_ping.py          # print alert (no Telegram)
python cloud_run.py           # scan + Telegram (needs env vars)
```

## Optional env

| Variable | Default | Meaning |
|----------|---------|---------|
| `MOMENTUM_TOP_N` | 8 | How many volatile names to track |
| `PING_MOVE_MIN_PCT` | 1.5 | Min 1-day % move to highlight |

## Other files

Older experiments (`momentum_plays.py`, `working_edge_system.py`) are not used by Railway anymore.
