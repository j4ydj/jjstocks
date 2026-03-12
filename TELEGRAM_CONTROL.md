# 📱 TELEGRAM-ONLY CONTROL

**Control your trading bot entirely from Telegram on your phone.**

---

## 🚀 How It Works

1. **Start the bot server** on your computer (one command)
2. **Send commands from Telegram** on your phone
3. **Bot runs scans remotely** and sends results back
4. **No need to touch terminal** - everything via Telegram

---

## 🏁 Quick Start

### Step 1: Start Bot Server (One Time)
```bash
cd /Users/home/stocks
./trading_bot.sh server
```

You'll see:
```
Starting Telegram bot server...
Bot will respond to commands in Telegram
Press Ctrl+C to stop
```

**Leave this running.** It can run 24/7.

### Step 2: Use From Your Phone

Open Telegram and send commands to your bot:

| Command | What It Does | Time |
|---------|--------------|------|
| `/start` | Show welcome | Instant |
| `/quick` | Scan 23 tickers | 2 min |
| `/full` | Scan 154 tickers | 7 min |
| `/all` | Scan 362 tickers | 15 min |
| `/longs` | Show buy signals | Instant |
| `/shorts` | Show sell signals | Instant |
| `/status` | Check bot status | Instant |
| `/help` | Show commands | Instant |

---

## 💬 Example Chat

**You:** `/start`

**Bot:**
```
🤖 Trading Bot Activated!

I'll scan the market for edge opportunities.

Commands:
/quick - Fast scan (23 tickers, 2 min)
/full - Full scan (154 tickers, 7 min)
/all - Complete scan (362 tickers, 15 min)
/longs - Top buy signals
/shorts - Top sell signals
/status - Bot status
/help - Show all commands

Just send a command to run a scan.
```

**You:** `/quick`

**Bot:**
```
⏳ Running quick scan (23 tickers)...
ETA: 2 minutes
```

*(2 minutes later)*

**Bot:**
```
✅ Quick Scan Complete

Scanned: 23 tickers
Signals: 5

🚀 LONG: 4
🔻 SHORT: 0
⚠️ AVOID: 1

Use /longs or /shorts for details.
```

**You:** `/longs`

**Bot:**
```
🎯 Top LONG Picks:

NVDA: +6 (HIGH)
Huge beat: +45.2%; PM wrong (30% expected)

TSLA: +4 (MEDIUM)
Good beat + Retail surge

PLTR: +3 (MEDIUM)
Retail interest spike
```

---

## 🔄 Running 24/7

### Option 1: Keep Terminal Open
```bash
./trading_bot.sh server
# Leave terminal running
```

### Option 2: Background Mode
```bash
# Run in background, logs to file
nohup ./trading_bot.sh server > bot_server.log 2>&1 &

# Check it's running
ps aux | grep telegram_bot_server

# View logs
tail -f bot_server.log

# Stop it later
ps aux | grep telegram_bot_server
kill <PID>
```

### Option 3: Auto-start on Boot (Mac)
Create `~/Library/LaunchAgents/tradingbot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>tradingbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/home/stocks/venv/bin/python</string>
        <string>/Users/home/stocks/telegram_bot_server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/home/stocks</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TELEGRAM_BOT_TOKEN</key>
        <string>8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/home/stocks/bot_server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/home/stocks/bot_server.error.log</string>
</dict>
</plist>
```

Activate:
```bash
launchctl load ~/Library/LaunchAgents/tradingbot.plist
launchctl start tradingbot
```

Now it runs even when you're not logged in!

---

## 📊 Daily Workflow (All From Phone)

**Morning:**
1. Open Telegram
2. Send `/full`
3. Wait 7 minutes
4. Review signals

**Midday:**
1. Send `/quick` for update
2. Check `/longs` for any new picks

**Evening:**
1. Send `/all` for complete market scan
2. Review overnight

**Anytime:**
- `/status` - Check if bot is running
- `/shorts` - See short signals
- `/help` - Forgot commands?

---

## 🔧 Troubleshooting

### "Bot not responding"
1. Check if server is running:
   ```bash
   ps aux | grep telegram_bot_server
   ```
2. If not running, restart:
   ```bash
   ./trading_bot.sh server
   ```

### "No output from commands"
- Bot might be busy with a scan
- Wait 2-15 minutes depending on command
- Check `/status`

### "Server stopped when I closed laptop"
Use background mode:
```bash
nohup ./trading_bot.sh server > bot_server.log 2>&1 &
```

Or use launchd (Option 3 above) for always-on.

---

## 🆚 Two Modes Explained

| Mode | How | When |
|------|-----|------|
| **CLI** | Run commands in terminal | Setup, debugging |
| **Telegram** | Send /commands to bot | Daily use, mobile |

**CLI Commands:**
```bash
./trading_bot.sh quick    # Run here, output here
./trading_bot.sh full     # Run here, output here
```

**Telegram Commands:**
```
/quick   # Run on computer, output to phone
/full    # Run on computer, output to phone
```

Both do the same scans - just different interface.

---

## 📝 Command Reference

| Command | Description | Response Time |
|---------|-------------|---------------|
| `/start` | Welcome & instructions | Instant |
| `/help` | Show all commands | Instant |
| `/quick` | 23 priority tickers | 2 min |
| `/full` | 154 high-potential | 7 min |
| `/all` | 362 full market | 15 min |
| `/longs` | Top buy signals | Instant |
| `/shorts` | Top sell signals | Instant |
| `/status` | Bot status | Instant |

---

## 🎯 Example Day

**9:00 AM (from bed):**
- Send `/full` to bot
- Shower, coffee
- Results arrive: 4 LONG signals found

**12:00 PM (at lunch):**
- Send `/quick`
- 2 minutes later: quick update
- Check if any new opportunities

**4:00 PM (market close):**
- Send `/all` for complete scan
- Review 362-ticker analysis

**All from your phone. No terminal needed.**

---

## ✅ Checklist

- [ ] Started server: `./trading_bot.sh server`
- [ ] Sent `/start` in Telegram
- [ ] Got welcome message back
- [ ] Ran `/quick` successfully
- [ ] Received scan results

**Once this works, you're fully mobile!**

---

## 🚀 Start Now

```bash
cd /Users/home/stocks
./trading_bot.sh server
```

Then open Telegram and send `/start`.

**That's it. You now control everything from your phone.**
