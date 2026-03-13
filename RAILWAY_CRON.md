# Railway cron schedule (UTC)

Railway runs cron in **UTC**. The repo is set for:

- **`0 14,17 * * 1-5`** = 14:00 UTC and 17:00 UTC, Monday–Friday

That is:

- **14:00 UTC** → 9:00 AM Eastern (EST) / 10:00 AM Eastern (EDT)
- **17:00 UTC** → 12:00 PM Eastern (EST) / 1:00 PM Eastern (EDT)

So you get a run in the morning and one around midday US Eastern.

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
