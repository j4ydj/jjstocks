# Momentum Chain Alerts

Map-based pipeline: volatile stocks → correlation chains → **predicted move, dates, entry/stop/target** → Telegram + tracked outcomes.

## Railway (automatic)

1. Deploy this repo on Railway (`python trigger_server.py` — in `railway.json`).
2. Set variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `CRON_SECRET` (random string)
   - `DATA_DIR=/data` with a volume mounted at `/data` (persists trades across deploys)
3. **GitHub auto-deploy** — push to `main` redeploys (repo connected on Railway).
4. **Daily scan** — `jjstocks-daily-cron` runs at **12:00 GMT** (UTC). Optional backup: GitHub Actions (see `scripts/setup_github_secret.sh`).

See `RAILWAY_DEPLOY.md` for URLs and manual triggers.

## Trade tracking

Every proposed trade → `data/trade_setups.jsonl`. Reports: `TRACKING_REPORT.md`, `SCOREBOARD.md`, `data/trade_tracker.csv`.

```bash
python3 daily_pipeline.py              # one scan (same as Railway /run)
python3 trade_tracker.py --fill        # refresh 1d/5d/10d + stop/target
python3 trade_tracker.py --report       # regenerate reports
python3 trade_tracker.py --dedupe      # compact duplicate log rows
```

Backtest validation: `python3 backtest_map_pipeline.py` → `BACKTEST_PIPELINE_RESULTS.md`

## Example Telegram message

```text
Pipeline alert
2026-05-19 12:00:00

Stock movements
  • RKLB $131.16  +2.1% today  (+5.0% / 5d)

Chain predictions & proposed trades

📉 SHORT RKLB  direct_follow
  Path: LUNR → RKLB
  Leader LUNR -3.2% → predict -1.9% by 2026-05-24 (5d, r=+0.75, hit 86%)
  Entry $131.16 · Stop $139.50 · Target $114.00 · Size ~30%
```

## Optional env

| Variable | Default | Meaning |
|----------|---------|---------|
| `PIPELINE_MIN_CORR` | 0.55 | Min correlation for a prediction |
| `PIPELINE_MIN_HIT` | 55 | Min OOS hit rate % |
| `PIPELINE_HOLD_DAYS` | 5 | Hold / expected horizon |
| `MOMENTUM_TOP_N` | 15 | Volatile names in scan |

## Other files

Older path (`chain_ping.py`, `chain_setups.py`) remains for comparison; Railway uses `daily_pipeline.py` via `cloud_run.py`.
