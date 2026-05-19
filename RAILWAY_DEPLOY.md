# Railway deployment — jjstocks

> Dashboard: https://railway.com/project/0a938466-f68c-4e1e-a086-a42d01601222

## Services

| Service | Role | Deploy |
|---------|------|--------|
| **jjstocks** | HTTP server (`trigger_server.py`) — health, manual `/run` | GitHub `main` → auto-deploy |
| **jjstocks-daily-cron** | Daily scan at **21:00 UTC** (after US close) | GitHub `main` → auto-deploy |

## Public URL (web service)

**https://jjstocks-production.up.railway.app**

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Uptime (no token) |
| `GET /run?token=CRON_SECRET` | Full scan + Telegram (~3–5 min) |
| `GET /run/outcomes?token=CRON_SECRET` | Refresh outcomes (~1 min) |

`CRON_SECRET`: Railway → **Variables** (both services) or local `.railway_cron_secret`.

## Daily schedule (21:00 UTC)

**Primary:** Railway cron on `jjstocks-daily-cron` — crontab `0 21 * * *` (UTC, ~US equity close).

Runs `scripts/cron_trigger.py`, which calls the web service `/run` then `/run/outcomes`.

**Backup:** GitHub Actions [`.github/workflows/daily-scan.yml`](.github/workflows/daily-scan.yml) at the same time. Requires one-time:

```bash
./scripts/setup_github_secret.sh   # needs: brew install gh && gh auth login
```

## GitHub auto-deploy

Repo **`j4ydj/jjstocks`** is connected to both Railway services. Every push to **`main`** redeploys.

CI workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs import checks on push (optional “Wait for CI” in Railway).

## Variables

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — on **jjstocks** (web)
- `CRON_SECRET` — on **jjstocks** and **jjstocks-daily-cron**
- `DATA_DIR=/data` — volume on **jjstocks** only

## Manual trigger

```bash
curl "https://jjstocks-production.up.railway.app/run?token=$(cat .railway_cron_secret)"
```

## Local CLI deploy (optional)

```bash
railway service jjstocks
railway up -d
```
