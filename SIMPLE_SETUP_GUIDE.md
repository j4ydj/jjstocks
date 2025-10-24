# 🤖 Simple Trading Bot - Setup Guide

## What This Is

A **stripped-back, working** Telegram bot for stock analysis. No complexity, no bloat - just:
- ✅ Real stock data from Yahoo Finance
- ✅ Basic technical analysis (RSI, MACD, Moving Averages)
- ✅ Simple Telegram interface
- ✅ Actually works!

## Quick Setup (3 Steps)

### 1. Get a Telegram Bot Token

1. Open Telegram and find **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy your bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Configure the Bot

Edit `trading_config.json` and set:
```json
{
  "TELEGRAM_BOT_TOKEN": "YOUR_TOKEN_HERE",
  "TELEGRAM_ENABLED": true,
  "WATCHLIST": ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]
}
```

### 3. Run the Bot

```bash
chmod +x start_simple.sh
./start_simple.sh
```

That's it! Now open Telegram and send `/start` to your bot.

## Commands

Once running, use these commands in Telegram:

- `/start` - Show main menu
- `/analyze TICKER` - Analyze any stock (e.g., `/analyze AAPL`)
- `/watchlist` - View your watchlist with prices
- `/scan` - Scan watchlist for buy/sell signals
- `/help` - Show help

You can also just send a ticker symbol like `AAPL` for a quick check.

## How It Works

The bot uses simple, proven technical analysis:

1. **RSI (Relative Strength Index)**
   - Below 30 = Oversold (potential buy)
   - Above 70 = Overbought (potential sell)

2. **Moving Averages**
   - Compares 20-day and 50-day averages
   - Price above both = bullish
   - Price below both = bearish

3. **MACD (Moving Average Convergence Divergence)**
   - MACD above signal = bullish
   - MACD below signal = bearish

The bot combines these to give a simple signal:
- 🟢 **BUY** - Multiple bullish indicators
- 🔴 **SELL** - Multiple bearish indicators  
- ⚪ **HOLD** - Mixed or neutral signals

## Customize Your Watchlist

Edit `trading_config.json`:
```json
{
  "WATCHLIST": [
    "AAPL",
    "TSLA", 
    "NVDA",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META"
  ]
}
```

Add any stocks you want to track. The bot will scan them when you use `/scan`.

## Troubleshooting

**Bot won't start:**
- Check your bot token in `trading_config.json`
- Make sure you have internet connection
- Try: `pip install -r simple_requirements.txt`

**Can't analyze a stock:**
- Check the ticker symbol is correct
- Some stocks might not have enough history
- Try a well-known stock like AAPL first

**Getting rate limited:**
- Yahoo Finance is free but has rate limits
- Wait a minute between large scans
- Keep your watchlist under 20 stocks

## What Was Removed

This simple version removed all the complex features that were breaking the system:
- ❌ Revolutionary intelligence
- ❌ Satellite data
- ❌ Blockchain analysis
- ❌ ML models
- ❌ Alternative data APIs
- ❌ Insider detection
- ❌ Reddit sentiment
- ❌ Web scraping
- ❌ 50+ configuration options

**Result:** A clean, working bot that does one thing well!

## Need More Features?

If this simple bot works well for you and you want to add features back, do it **one at a time**:
1. Test each feature independently
2. Make sure it doesn't break the bot
3. Only add if you really need it

Keep it simple and it will keep working! 📈

