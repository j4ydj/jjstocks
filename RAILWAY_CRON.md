# Railway cron schedule (UTC)

Railway runs cron in **UTC**. All times below are UTC.

## Current schedule: UK open to US close, every hour

- **`0 7,8,9,10,11,12,13,14,15,16,17,18,19,20,21 * * 1-5`** = at :00 past the hour, 07:00–21:00 UTC, Mon–Fri = **15 runs/day**


| UTC  | UK (GMT) | UK (BST) | US Eastern (EST) | US Eastern (EDT) |
|------|----------|----------|------------------|------------------|
| 07:00 | 7:00 AM  | 8:00 AM  | 2:00 AM          | 3:00 AM          |
| 08:00 | 8:00 AM  | 9:00 AM  | 3:00 AM          | 4:00 AM          |
| 14:00 | 2:00 PM  | 3:00 PM  | 9:00 AM          | 10:00 AM         |
| 21:00 | 9:00 PM  | 10:00 PM | 4:00 PM          | 5:00 PM          |

Start = UK open (8am GMT/BST). End = US close (4pm Eastern). One scan per hour in that window.

**Every 30 min instead?** Use `"schedule": "0,30 7,8,9,10,11,12,13,14,15,16,17,18,19,20,21 * * 1-5"` (30 runs/day; heavier on free tier).

## Free tier: how much is “too much”?

- **Railway free tier** = about **$1/month** credit. You’re charged for compute only while the job runs.
- **This job** ≈ 2–3 minutes per run (93 tickers, APIs, etc.).
- **Minimum interval** Railway allows between cron runs = **5 minutes**.

Rough guide:

| Schedule                    | Runs/day | Compute/day | Note        |
|----------------------------|----------|-------------|-------------|
| UK open–US close, hourly   | 15       | ~40 min     | **Current** |
| UK open–US close, 30 min   | 30       | ~75 min     | Optional    |
| Every 5 min                | 78+      | 3+ hours    | Will burn $1 |

Hourly (15 runs/day) is reasonable on the free $1. Every 30 min (30 runs/day) is possible but uses more credit.

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

**UK open to US close, every 30 min (30 runs/day):**
```json
"schedule": "0,30 7,8,9,10,11,12,13,14,15,16,17,18,19,20,21 * * 1-5"
```

**Once at market open (9:30am Eastern ≈ 14:30 UTC):**
```json
"schedule": "30 14 * * 1-5"
```
