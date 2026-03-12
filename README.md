# Trading Bot

Cloud-deployed trading signal generator with Telegram alerts.

## Quick Start

```bash
# Deploy to Railway (cloud)
1. Push to GitHub
2. Connect to Railway
3. Bot runs 24/7 automatically
```

## Core Files

| File | Purpose |
|------|---------|
| `cloud_run.py` | Cloud entry point (Railway/AWS/GCP) |
| `working_edge_system.py` | Main signal generation |
| `telegram_alerts.py` | Telegram integration |
| `railway.json` | Railway configuration |
| `requirements.txt` | Dependencies |

## Data Sources

- `prediction_markets.py` - Polymarket odds
- `retail_sentiment_edge.py` - Wikipedia + Reddit + Google Trends
- `wikipedia_views.py` - Wikipedia traffic
- `sec_filing_risk.py` - SEC filing analysis
- `sentiment_intelligence.py` - Reddit sentiment
- `google_trends.py` - Google Trends

## Analysis

- `earnings_drift.py` - Earnings surprise detection
- `backtest.py` - Strategy backtesting
- `run_winning_strategy.py` - Earnings strategy runner

## Utilities

- `telegram_bot_server.py` - Telegram bot server
- `market_wide_scanner.py` - Multi-ticker scanner
- `auto_runner.py` - Local automation
- `fast_scan.py` - Quick scan utility
- `setup_telegram.py` - Telegram setup helper
- `trading_bot.sh` - CLI control script

## Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Deployment

See `DEPLOY_TO_RAILWAY.md` for full instructions.

## License

Private
