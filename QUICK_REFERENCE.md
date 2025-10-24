# ⚡ Quick Reference Card

## 🚀 To Start The Bot

```bash
./start_simple.sh
```

Then open Telegram and send `/start` to your bot.

---

## 📱 Telegram Commands

| Command | What It Does |
|---------|-------------|
| `/start` | Show main menu |
| `/analyze AAPL` | Analyze any stock |
| `/watchlist` | View your watchlist |
| `/scan` | Scan for signals |
| `/help` | Show help |

**Quick tip:** Just send `TSLA` for instant price check!

---

## 📁 Files To Use

✅ **Use These:**
```
simple_trading_bot.py          ← Run this
simple_requirements.txt        ← Install from this
trading_config.json            ← Your config (edit bot token)
start_simple.sh               ← Startup script
```

📚 **Documentation:**
```
START_HERE.md                 ← Start here!
README_SIMPLE.md              ← Full docs
SIMPLE_SETUP_GUIDE.md         ← Setup guide
SYSTEM_COMPARISON.md          ← Old vs New comparison
QUICK_REFERENCE.md            ← This file
```

🧪 **Testing:**
```
test_simple_bot.py            ← Test before running
```

❌ **Ignore These (Old System):**
```
personal_trading_system.py     ← 82k lines (too complex)
trading_telegram_bot.py        ← Old entry point
requirements.txt               ← Old dependencies
All other .py files            ← Complex old features
```

---

## ⚙️ Configuration

Edit `trading_config.json`:

```json
{
  "TELEGRAM_BOT_TOKEN": "YOUR_TOKEN_FROM_BOTFATHER",
  "TELEGRAM_ENABLED": true,
  "WATCHLIST": ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]
}
```

Get bot token: Message **@BotFather** on Telegram → `/newbot`

---

## 🔧 Common Commands

```bash
# Test first
python3 test_simple_bot.py

# Run bot
./start_simple.sh

# Or manually
pip3 install -r simple_requirements.txt
python3 simple_trading_bot.py

# Check logs
tail -f simple_bot.log

# Stop bot
Ctrl+C
```

---

## 📊 Signal Meanings

| Signal | Meaning | What To Do |
|--------|---------|------------|
| 🟢 **BUY** | Multiple bullish indicators | Consider buying |
| 🔴 **SELL** | Multiple bearish indicators | Consider selling |
| ⚪ **HOLD** | Mixed/neutral signals | Wait for better signal |

**Not financial advice!** Always do your own research.

---

## 🔍 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Module not found" | `pip3 install -r simple_requirements.txt` |
| "Invalid token" | Check bot token in `trading_config.json` |
| "Can't analyze stock" | Check ticker symbol (AAPL not Apple) |
| Bot doesn't respond | Send `/start` and check you're in right chat |
| Rate limit errors | Wait 1 minute, keep watchlist under 20 stocks |

**Still stuck?** Check `simple_bot.log` for errors.

---

## 📈 How It Works

1. **Fetches data** from Yahoo Finance (free)
2. **Calculates indicators:**
   - RSI (overbought/oversold)
   - Moving averages (20 & 50 day)
   - MACD (momentum)
3. **Scores signal** based on multiple factors
4. **Returns BUY/SELL/HOLD** with reasoning

Simple, proven, reliable! ✅

---

## ✅ What You Get

✅ Real stock data  
✅ Technical analysis  
✅ Simple signals  
✅ Telegram interface  
✅ Watchlist scanning  
✅ 100% free  
✅ Fast & reliable  

## ❌ What Was Removed

❌ ML/AI models  
❌ Satellite data  
❌ Blockchain analysis  
❌ 50+ complex features  
❌ Paid APIs  
❌ Web scraping  
❌ Constant breakage  

---

## 💡 Tips

1. **Test first:** Run `test_simple_bot.py` before the bot
2. **Start simple:** Use the default watchlist first
3. **Check signals:** Don't blindly follow, use as one input
4. **Keep it small:** Under 20 stocks in watchlist
5. **One feature:** If adding features, do one at a time

---

## 📚 Learn More

- `START_HERE.md` - Complete overview
- `README_SIMPLE.md` - Full documentation
- `SIMPLE_SETUP_GUIDE.md` - Detailed setup
- `SYSTEM_COMPARISON.md` - Old vs new analysis

---

## ⚡ TL;DR

```bash
# 1. Get bot token from @BotFather on Telegram
# 2. Put it in trading_config.json
# 3. Run:
./start_simple.sh
# 4. Open Telegram, send /start
# 5. Done! 🎉
```

**That's it. Simple, clean, working.** 📈

---

*Keep this file handy for quick reference!* 🔖

