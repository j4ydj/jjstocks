# 🤖 Simple Trading Bot

**A clean, working Telegram bot for stock analysis** 📈

## What Is This?

Your trading system was broken with 82,000 lines of complex code. This is a **stripped-back version that actually works**.

### What It Does
- ✅ Analyzes stocks using real Yahoo Finance data
- ✅ Uses proven technical indicators (RSI, MACD, Moving Averages)
- ✅ Provides simple BUY/SELL/HOLD signals
- ✅ Works via Telegram on your phone
- ✅ Scans your watchlist for opportunities

### What It Doesn't Do
- ❌ No ML models
- ❌ No satellite data
- ❌ No blockchain analysis
- ❌ No web scraping
- ❌ No 50+ complex features that break

**Result:** Simple, fast, reliable.

---

## Quick Start (5 Minutes)

### Step 1: Get Telegram Bot Token

1. Open Telegram, search for **@BotFather**
2. Send `/newbot` and follow instructions
3. Copy your bot token (looks like `1234567890:ABC...xyz`)

### Step 2: Configure

Option A - Use existing config:
```bash
# Edit your existing trading_config.json
# Make sure it has these fields:
{
  "TELEGRAM_BOT_TOKEN": "your_token_here",
  "TELEGRAM_ENABLED": true,
  "WATCHLIST": ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]
}
```

Option B - Use simple config template:
```bash
cp simple_config.json trading_config.json
# Then edit trading_config.json with your bot token
```

### Step 3: Run

```bash
./start_simple.sh
```

Or manually:
```bash
./venv/bin/pip install -r simple_requirements.txt
./venv/bin/python simple_trading_bot.py
```

### Step 4: Use It!

Open Telegram, find your bot, and send: `/start`

---

## Commands

| Command | What It Does |
|---------|-------------|
| `/start` | Show main menu with buttons |
| `/analyze AAPL` | Get full analysis of any stock |
| `/watchlist` | View your watchlist with current prices |
| `/scan` | Scan watchlist for BUY/SELL signals |
| `/help` | Show help message |

**Quick tip:** You can just send a ticker like `TSLA` for a fast price check!

---

## How It Works

The bot uses classic technical analysis:

### 1. RSI (Relative Strength Index)
- **RSI < 30** = Oversold → Potential BUY
- **RSI > 70** = Overbought → Potential SELL
- **RSI 30-70** = Neutral

### 2. Moving Averages
- **20-day SMA** = Short-term trend
- **50-day SMA** = Medium-term trend
- **Price above both** = Bullish 📈
- **Price below both** = Bearish 📉

### 3. MACD (Moving Average Convergence Divergence)
- **MACD > Signal line** = Bullish momentum
- **MACD < Signal line** = Bearish momentum

### 4. Signal Scoring
The bot combines all indicators into a score:
- **Score ≥ +2** = 🟢 **BUY** signal
- **Score ≤ -2** = 🔴 **SELL** signal
- **Score between** = ⚪ **HOLD** (neutral)

---

## Example Analysis

```
📊 AAPL Analysis

💰 Price: $175.50 (+1.25%)

Technical Indicators:
• RSI: 45.2
• SMA 20: $172.30
• SMA 50: $168.75
• MACD: 2.15
• Signal: 1.80

Signal: 🟢 BUY (Score: 3)

Reasoning:
• Price above MAs
• Golden cross (20>50)
• MACD bullish
```

---

## Customize Your Watchlist

Edit `trading_config.json`:

```json
{
  "WATCHLIST": [
    "AAPL",    "TSLA",    "NVDA",
    "MSFT",    "GOOGL",   "AMZN",
    "META",    "AMD",     "NFLX",
    "COIN",    "PLTR",    "SOFI"
  ]
}
```

Add any stocks you want. The `/scan` command will check all of them!

**Tip:** Keep it under 20 stocks to avoid rate limits.

---

## Files

### Use These (Simple System)
```
simple_trading_bot.py          ← Main bot (clean, 400 lines)
simple_requirements.txt        ← Minimal dependencies
simple_config.json             ← Config template
start_simple.sh               ← Easy startup script
test_simple_bot.py            ← Test before running
SIMPLE_SETUP_GUIDE.md         ← Detailed setup
README_SIMPLE.md              ← This file
MIGRATION_TO_SIMPLE.md        ← Migration guide
```

### Old Files (Backup)
Your old complex system is still there:
```
personal_trading_system.py     ← 82k lines (too complex)
trading_telegram_bot.py        ← Old entry point
requirements.txt               ← 50+ packages
```

I didn't delete anything, but I recommend using the simple system.

---

## Testing

Before running the bot, test that everything works:

```bash
./venv/bin/python test_simple_bot.py
```

This checks:
- ✅ All packages installed
- ✅ Config file exists
- ✅ Stock data works
- ✅ Signal generation works
- ✅ Bot can initialize

If all tests pass, you're ready to run!

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'yfinance'"
```bash
pip3 install -r simple_requirements.txt
```

### "Config file not found"
```bash
cp simple_config.json trading_config.json
# Then edit trading_config.json with your bot token
```

### "Invalid bot token"
- Check for typos in `trading_config.json`
- Make sure no extra spaces around the token
- Get a new token from @BotFather if needed

### "Could not analyze TICKER"
- Check the ticker symbol is correct (AAPL not Apple)
- Some penny stocks might not have data
- Try a major stock like AAPL or TSLA first

### Bot doesn't respond in Telegram
- Make sure you're messaging the correct bot
- Try `/start` command
- Check logs: `tail -f simple_bot.log`
- Verify bot token is correct

### Rate limit errors
- Yahoo Finance has free rate limits
- Wait a minute between large scans
- Keep watchlist under 20 stocks
- Don't run multiple scans simultaneously

---

## Advantages

| Simple Bot | Old System |
|------------|------------|
| ✅ 400 lines of code | ❌ 82,000 lines |
| ✅ 6 packages | ❌ 50+ packages |
| ✅ 5-minute setup | ❌ Hours of config |
| ✅ Works reliably | ❌ Always breaking |
| ✅ Easy to debug | ❌ Impossible to debug |
| ✅ Fast responses | ❌ Slow and laggy |
| ✅ Free data | ❌ Paid APIs needed |

---

## Adding Features

Want to add more features? Do it **one at a time**:

### ✅ Good Features to Add
1. Email alerts (simple SMTP)
2. Price alerts at specific levels
3. Portfolio value tracking
4. More technical indicators
5. Basic news headlines

### ⚠️ Add Carefully
- Machine learning (test extensively)
- Sentiment analysis (can be noisy)
- Multiple data sources (more failure points)

### ❌ Don't Add (Too Complex)
- Satellite intelligence
- Blockchain whale tracking
- Revolutionary data sources
- Web scraping (breaks constantly)
- 20+ alternative data APIs

**Rule:** Only add what you actually need. Complexity kills reliability.

---

## Philosophy

> "Perfection is achieved not when there is nothing more to add,
> but when there is nothing left to take away."
> — Antoine de Saint-Exupéry

This bot follows that principle:
- Does one thing well (stock analysis)
- Uses reliable data (Yahoo Finance)
- Simple proven indicators
- Clean, maintainable code
- Actually works!

**A working simple system beats a broken complex system every time.** 📈

---

## Support

### Documentation
- `SIMPLE_SETUP_GUIDE.md` - Detailed setup instructions
- `MIGRATION_TO_SIMPLE.md` - Why and how we simplified
- This file - Quick reference

### Logs
```bash
# View bot logs
tail -f simple_bot.log

# View last 50 lines
tail -n 50 simple_bot.log
```

### Common Issues
1. Most issues are config problems (bot token)
2. Test with `test_simple_bot.py` first
3. Try analyzing AAPL before your own stocks
4. Check you have internet connection
5. Verify you're messaging the right bot

---

## What's Next?

1. **Get it running** - Follow Quick Start
2. **Test it** - Try `/analyze AAPL`
3. **Customize** - Edit your watchlist
4. **Use it** - Set up `/scan` to run regularly
5. **Expand** - Add ONE feature at a time if needed

**Don't try to rebuild the complex system.** Start simple, stay reliable.

---

## Technical Details

**Language:** Python 3.8+  
**Data Source:** Yahoo Finance (yfinance)  
**Bot Framework:** python-telegram-bot 20.0+  
**Analysis:** Technical indicators only  
**Update Frequency:** On demand (no background scanning)

**Dependencies:**
```
yfinance       - Stock data
pandas         - Data processing
numpy          - Calculations
python-telegram-bot - Bot interface
```

---

## License & Disclaimer

This is a personal trading tool. Not financial advice.

**Use at your own risk.** Always do your own research before making trading decisions.

The bot provides technical analysis signals, but:
- ❌ Not guaranteed to be profitable
- ❌ Past performance ≠ future results
- ❌ Markets can be irrational
- ❌ Technical analysis isn't always accurate

**Never trade money you can't afford to lose.**

---

## Contributing

Found a bug? Want to improve something?

1. Keep changes **simple**
2. Test thoroughly before committing
3. Don't add complex dependencies
4. Maintain the "simple" philosophy

---

## Version

**Simple Trading Bot v1.0**  
*Built: 2025*  
*Status: Stable and working*

---

**Ready to get started?**

```bash
./start_simple.sh
```

Then open Telegram and send `/start` to your bot! 🚀

