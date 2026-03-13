# Railway cron schedule (UTC)

Railway runs cron in **UTC**. All times below are UTC.

## Current schedule: hourly during US market hours

- **`0 14,15,16,17,18,19,20 * * 1-5`** = at :00 past the hour, 14:00–20:00 UTC, Mon–Fri

That’s **7 runs per day** during the US session:

| UTC  | Eastern (EDT) | Eastern (EST) |
|------|----------------|----------------|
| 14:00 | 10:00 AM      | 9:00 AM        |
| 15:00 | 11:00 AM      | 10:00 AM       |
| 16:00 | 12:00 PM      | 11:00 AM       |
| 17:00 | 1:00 PM       | 12:00 PM       |
| 18:00 | 2:00 PM       | 1:00 PM        |
| 19:00 | 3:00 PM       | 2:00 PM        |
| 20:00 | 4:00 PM       | 3:00 PM        |

So you get a scan every hour from market open through mid-afternoon Eastern.

## Free tier: how much is “too much”?

- **Railway free tier** = about **$1/month** credit. You’re charged for compute only while the job runs.
- **This job** ≈ 2–3 minutes per run (93 tickers, APIs, etc.).
- **Minimum interval** Railway allows between cron runs = **5 minutes**.

Rough guide:

| Schedule              | Runs/day | Compute/day | Risk on $1/mo |
|-----------------------|----------|-------------|----------------|
| 2x (9am, 12pm)        | 2        | ~6 min      | Very low       |
| **Hourly (current)**  | **7**    | **~20 min** | **Low**        |
| Every 30 min          | 14       | ~40 min     | Medium         |
| Every 15 min          | 28       | ~80 min     | High           |
| Every 5 min           | 78       | ~3+ hours   | Will burn $1   |

Sticking to **hourly (7 runs/day)** or **twice daily** is safe. Going to every 30 min or more often can use up the free credit in a couple of weeks.

## If it didn’t run

1. **Wrong time** – Check the Railway run time in UTC and convert to your zone. If you want different times, change the hours in `railway.json` (always in UTC).
2. **Cron not set in Railway** – In the dashboard: Service → **Settings** → **Cron Schedule**. It must match what’s in `railway.json` (or override it there). Save after editing.
3. **Previous run still active** – If a run is still “Active”, the next one is skipped. Check **Deployments** / **Logs** for a run that never exited (e.g. hang or error).
4. **Build/deploy failed** – If the latest deploy failed, cron may be using an old or broken version. Check **Deployments** for a successful deploy.

## Changing the times (UTC reference)

| Local (Eastern) | UTC (EST) | UTC (EDT) |
|-----------------|-----------|-----------|
| 9:00 AM         | 14:00     | 13:00     |
| 12:00 PM        | 17:00     | 16:00     |
| 4:00 PM         | 21:00     | 20:00     |

Edit the `schedule` in `railway.json`, then redeploy. If you set cron only in the Railway UI, that overrides the file.

## Other schedule options (copy into `railway.json`)

**Twice per day (9am + 12pm Eastern):**
```json
"schedule": "0 14,17 * * 1-5"
```

**Every 30 min during market hours (higher usage):**
```json
"schedule": "0,30 14,15,16,17,18,19,20 * * 1-5"
```

**Once at market open (9:30am Eastern ≈ 14:30 UTC):**
```json
"schedule": "30 14 * * 1-5"
```
