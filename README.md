# Edge System

Multi-factor trading signal generator. Only outputs actionable trades when 3+ independent signals confirm.

## How It Works

5 signal layers, all free data:

| Signal | Source | What It Detects |
|--------|--------|----------------|
| TREND | yfinance | Price vs 20/50 MA |
| MOMENTUM | yfinance | Relative strength vs SPY |
| VOLUME | yfinance | Unusual accumulation/distribution |
| EARNINGS | yfinance | Post-earnings surprise drift |
| ATTENTION | Wikipedia API | Pageview anomalies |

Plus SEC filing risk filter (hard reject on going concern / material weakness).

**Minimum 3 of 5 signals must agree on direction.** No trade is generated otherwise.

## Output

Every trade includes: entry, stop loss, target, risk/reward, position size, exit date.

## Deployment

Runs on Railway (free tier, serverless cron). Sends alerts to Telegram.

## Files

| File | Purpose |
|------|---------|
| `working_edge_system.py` | Core signal engine |
| `cloud_run.py` | Cloud entry point |
| `telegram_alerts.py` | Telegram alerts |
| `sec_filing_risk.py` | SEC EDGAR risk filter |
| `wikipedia_views.py` | Wikipedia attention tracking |
| `earnings_drift.py` | Earnings surprise detection |
| `railway.json` | Railway config |
| `requirements.txt` | Dependencies |
