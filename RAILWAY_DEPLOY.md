# Railway deployment — jjstocks

> Live as of 2026-05-19. Dashboard: https://railway.com/project/0a938466-f68c-4e1e-a086-a42d01601222

## Public URL

**https://jjstocks-production.up.railway.app**

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Uptime check (no token) |
| `GET /run?token=CRON_SECRET` | Daily scan + Telegram + log trades (~3–5 min) |
| `GET /run/outcomes?token=CRON_SECRET` | Refresh 1d/5d/10d outcomes + reports (~1 min) |

`CRON_SECRET` is in Railway → **jjstocks** → **Variables**, and locally in `.railway_cron_secret` (gitignored).

## cron-job.org

1. **Scan** — hourly Mon–Fri, 07:00–21:00 UTC, **timeout 5 minutes**:
   ```text
   https://jjstocks-production.up.railway.app/run?token=YOUR_CRON_SECRET
   ```
2. **Outcomes** — once daily, **timeout 2 minutes**:
   ```text
   https://jjstocks-production.up.railway.app/run/outcomes?token=YOUR_CRON_SECRET
   ```

## Variables (already set)

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `CRON_SECRET`
- `DATA_DIR=/data`

## Volume

Persistent volume **`jjstocks-volume`** mounted at **`/data`** (trade log survives redeploys).

## Redeploy from your machine

```bash
cd /path/to/stocks
railway link   # pick jjstocks if needed
railway up -d
```

## GitHub auto-deploy (optional)

Railway project was created via CLI (`railway up`). To deploy on every `git push`:

1. Open the [project dashboard](https://railway.com/project/0a938466-f68c-4e1e-a086-a42d01601222)
2. **jjstocks** service → **Settings** → **Connect Repo** → `j4ydj/jjstocks`
3. Disable duplicate deploys if you keep using `railway up` manually
