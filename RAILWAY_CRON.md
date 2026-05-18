# Serverless + External Cron (cron-job.org)

The app runs as a **serverless web service**. There is **no Railway cron**; an **external cron** (e.g. cron-job.org) calls a URL to trigger the scan.

---

## 1. Railway: set env and deploy

1. In Railway: your service → **Variables**.
2. Add:
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (already there).
   - **`CRON_SECRET`** = a random string only you know (e.g. `openssl rand -hex 16`). Used to protect the trigger URL.
3. Deploy. The service runs **`python trigger_server.py`**: it listens on `PORT` and waits for HTTP requests.

---

## 2. Get your public URL

- Railway gives you a public URL (e.g. `https://your-app.up.railway.app`).
- If you use a custom domain, use that. The trigger path is **`/run`** (or `/` or `/cron`).

**Full trigger URL:**

```text
https://YOUR-RAILWAY-URL/run?token=YOUR_CRON_SECRET
```

Example: if your URL is `https://stocks-abc.up.railway.app` and `CRON_SECRET` is `mySecret123`:

```text
https://stocks-abc.up.railway.app/run?token=mySecret123
```

---

## 3. Set up cron-job.org (or similar)

1. Go to [cron-job.org](https://cron-job.org) and create a free account.
2. **Create Cronjob**:
   - **URL:** `https://YOUR-RAILWAY-URL/run?token=YOUR_CRON_SECRET`
   - **Schedule:** e.g. every hour from UK open to US close, Mon–Fri (see below).
3. Save. The cronjob will GET that URL at the chosen times; the server will run the scan and send Telegram alerts.

**Suggested schedule (15 runs/day, like before):**  
Run at **:00** past the hour, for hours **7–21 UTC**, **Mon–Fri**. In cron-job.org you can use “Every hour” and then set a time range, or use “Custom” and enter something equivalent (e.g. 15 runs: 07:00, 08:00, …, 21:00 UTC on weekdays).

---

## 4. cron-job.org: set timeout to 5 minutes

The scan takes **2–5+ minutes**. In cron-job.org, set the request **timeout to 5 minutes** (or the maximum allowed). Otherwise the cron may show "failed" even though the scan completes on Railway and Telegram is sent.

- **Health check (no token):** `https://YOUR-RAILWAY-URL/health` → should return `{"ok": true, "status": "up"}` immediately.

## 5. Check it works

- **Manual test:** open in browser (or `curl`):
  ```text
  https://YOUR-RAILWAY-URL/run?token=YOUR_CRON_SECRET
  ```
  Wait 2–5 minutes. You should get JSON `{"ok": true, "message": "OK"}` and see a scan in Railway logs; Telegram gets **one chain alert** (what moved + what follows, with prices).
- **Wrong/missing token:** HTTP 403.
- **CRON_SECRET not set in Railway:** HTTP 503 and a message to set it.

---

## Time reference (UTC)

| UTC  | UK (GMT) | US Eastern (EST) |
|------|----------|------------------|
| 07:00 | 7:00 AM  | 2:00 AM          |
| 14:00 | 2:00 PM  | 9:00 AM          |
| 21:00 | 9:00 PM  | 4:00 PM          |

So 07:00–21:00 UTC = UK open to US close, hourly = 15 triggers/day on weekdays.

---

## Security

- **Keep `CRON_SECRET` secret.** Anyone with the full URL can trigger a scan (and spend a bit of your Railway compute).
- Don’t commit `CRON_SECRET` to the repo; only in Railway Variables (and in cron-job.org URL).

---

## If it still doesn’t run – checklist

| Check | What to do |
|-------|------------|
| **Code deployed?** | Latest push must be deployed. Railway → **Deployments** → latest is success and includes `trigger_server.py`. |
| **CRON_SECRET set?** | Railway → **Variables** → `CRON_SECRET` = same value you use in the URL. No spaces; case-sensitive. |
| **URL exact?** | Use `https://YOUR-APP.up.railway.app/run?token=YOUR_CRON_SECRET`. Replace both placeholders. |
| **Generate domain?** | Railway → **Settings** → **Networking** → generate a public domain if you don’t have one. |
| **cron-job.org** | Create the cronjob with the URL above. Set **timeout to 5 minutes**. Check **Execution history** for the last run (success / timeout / error). |
| **Telegram** | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` must be in Railway Variables. Test the bot manually (e.g. send a message from the bot). |
| **Railway logs** | After a trigger time, open **Logs**. You should see “Trigger server listening…” and then “Chain scan started”. If you see 403/503, the URL or token is wrong. |

**Quick test from your machine:**

```bash
# Replace with your real URL and token
curl -v "https://YOUR-RAILWAY-URL/health"
curl -v "https://YOUR-RAILWAY-URL/run?token=YOUR_CRON_SECRET"
```

- `/health` should return 200 and `{"ok": true}` with no token.
- `/run?token=...` with the right token starts the scan (may take 2–5 min to respond).

---

## Trade tracking (proposed trades)

Every scan logs to **`data/trade_setups.jsonl`** (proposed trades + scan heartbeats). Outcomes (1d/5d/10d, stop/target hit) update automatically after each scan.

### Persist logs on Railway (required for long-term tracking)

Railway’s disk is **ephemeral** by default — logs are lost on redeploy unless you add a volume:

1. Railway → your service → **Volumes** → Add volume (e.g. 1 GB), mount path **`/data`**
2. Variables → **`DATA_DIR`** = `/data`
3. Redeploy

Local runs use `./data` automatically.

### Second cron: daily outcome refresh (optional)

Add a lightweight cron-job (once daily, e.g. 22:00 UTC Mon–Fri):

```text
https://YOUR-RAILWAY-URL/run/outcomes?token=YOUR_CRON_SECRET
```

Timeout 2 minutes is enough. Refreshes forward returns and writes `TRACKING_REPORT.md` on the server.

### Review performance locally

```bash
python trade_tracker.py --fill
python trade_tracker.py --report   # → TRACKING_REPORT.md + data/trade_tracker.csv
```

Open **`data/trade_tracker.csv`** in Excel to validate every proposed trade over time.
