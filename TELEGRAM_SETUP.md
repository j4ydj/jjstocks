# 📱 TELEGRAM AUTOMATION SETUP

Complete guide to automate trading signals via Telegram.

---

## 🚀 Quick Start (5 Minutes)

### 1. Run Interactive Setup
```bash
cd /Users/home/stocks
python setup_telegram.py
```

Follow prompts to:
1. Create bot via @BotFather
2. Get your chat ID from @userinfobot
3. Test connection

### 2. Activate Configuration
```bash
source .telegram_config
```

### 3. Run First Scan
```bash
python telegram_alerts.py
```

---

## 📋 Manual Setup

If you prefer manual setup:

### Step 1: Create Telegram Bot
1. Open Telegram, search for **@BotFather**
2. Click **Start**
3. Send: `/newbot`
4. Choose name: `My Trading Bot`
5. Choose username: `mytrades_bot` (must end in 'bot')
6. **Copy the token** (looks like: `8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8`)

### Step 2: Get Your Chat ID
1. Search for **@userinfobot**
2. Click **Start**
3. **Copy your ID** (looks like: `123456789`)

### Step 3: Set Environment Variables
```bash
# Add to your ~/.zshrc or ~/.bashrc
export TELEGRAM_BOT_TOKEN='8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8'
export TELEGRAM_CHAT_ID='your_chat_id'
```

Reload:
```bash
source ~/.zshrc
```

### Step 4: Test
```bash
python telegram_alerts.py --test
```

---

## ⏰ Automation Options

### Option 1: Schedule (Recommended)
```bash
# Daily morning scan
python auto_runner.py --schedule daily

# Market open
python auto_runner.py --schedule market_open

# Pre-market + market open + midday
python auto_runner.py --schedule pre_market
```

### Option 2: Cron Job (Mac/Linux)
```bash
# Edit crontab
crontab -e

# Add these lines:
# Daily at 7:00 AM
0 7 * * * cd /Users/home/stocks && venv/bin/python auto_runner.py --once >> /Users/home/stocks/cron.log 2>&1

# Market open (9:30 AM ET, Mon-Fri)
30 9 * * 1-5 cd /Users/home/stocks && venv/bin/python auto_runner.py --once --quick >> /Users/home/stocks/cron.log 2>&1

# Midday (12:00 PM ET, Mon-Fri)
0 12 * * 1-5 cd /Users/home/stocks && venv/bin/python auto_runner.py --once --quick >> /Users/home/stocks/cron.log 2>&1
```

### Option 3: Launch Agent (Mac)
Create `~/Library/LaunchAgents/com.tradingbot.scan.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tradingbot.scan</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/home/stocks/venv/bin/python</string>
        <string>/Users/home/stocks/auto_runner.py</string>
        <string>--once</string>
        <string>--quick</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>30</integer>
            <key>Weekday</key>
            <integer>1</integer>
        </dict>
        <!-- Repeat for Mon-Fri -->
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/home/stocks</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TELEGRAM_BOT_TOKEN</key>
        <string>8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8</string>
        <key>TELEGRAM_CHAT_ID</key>
        <string>YOUR_CHAT_ID</string>
    </dict>
</dict>
</plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.tradingbot.scan.plist
```

### Option 4: Run in Background
```bash
# Run full scan every hour
python auto_runner.py --loop 60

# Run in background (daemon)
nohup python auto_runner.py --loop 60 > bot.log 2>&1 &
```

---

## 📊 Alert Types

### Daily Summary
```
📊 Daily Edge Scan Complete

Scanned: 154 tickers
Signals found: 23

🚀 LONG: 15
🔻 SHORT: 3
⚠️ AVOID: 5
```

### High Confidence Signal
```
🚀 NVDA | Score: +6

Direction: LONG
Confidence: HIGH 🔥
Sources: earnings, PM, retail

Catalyst:
Huge beat: +45.2%
PM wrong (30% expected failure)
Retail surge (strength: 0.85)
```

### Quick Alert
```
⚠️ ARKK | Score: -5

Direction: AVOID
SEC risk detected in 10-K
```

---

## 🔧 Commands Reference

### One-time scans
```bash
# Quick scan (23 tickers, ~2 min)
python telegram_alerts.py

# Full scan (154 tickers, ~7 min)
python telegram_alerts.py  # (uses priority universe by default)

# Custom universe
python -c "
from telegram_alerts import TelegramBot
from working_edge_system import WorkingEdgeSystem
bot = TelegramBot()
system = WorkingEdgeSystem()
signals = system.scan(['AAPL', 'TSLA', 'GME'], min_score=2)
for s in signals:
    bot.send_signal_alert({'ticker': s.ticker, 'score': s.score, ...})
"
```

### Scheduled
```bash
# Morning routine
python auto_runner.py --schedule daily

# Market hours only
python auto_runner.py --schedule market_open

# Every 2 hours during market
python auto_runner.py --loop 120
```

### Testing
```bash
# Test Telegram connection
python telegram_alerts.py --test

# Test with mock data
python telegram_alerts.py --dry-run

# Check logs
tail -f auto_runner.log
tail -f bot.log
```

---

## 🛠️ Troubleshooting

### "Bot not configured"
```bash
# Check environment variables
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID

# If empty, reload config
source .telegram_config

# Or set directly
export TELEGRAM_BOT_TOKEN='8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8'
export TELEGRAM_CHAT_ID='your_chat_id'
```

### "Failed to send message"
- Check bot token is correct (get from @BotFather)
- Check chat ID is correct (get from @userinfobot)
- Make sure you started chat with bot (/start)
- Check bot isn't blocked

### Rate limits
- Default delay: 0.3s between tickers
- If Yahoo blocks: Increase delay in `market_wide_scanner.py`
- Google Trends: Max 100 req/min (built-in limit)

### Cron not running
```bash
# Check cron is installed
which crontab

# Check cron service
sudo launchctl list | grep cron  # Mac
service cron status  # Linux

# Check logs
tail -f /var/log/cron
```

---

## 📝 Configuration Files

| File | Purpose |
|------|---------|
| `.telegram_config` | Bot token and chat ID |
| `auto_runner_state.json` | Run counter, last run time |
| `auto_runner.log` | Activity log |
| `scan_*.json` | Scan results with timestamps |
| `market_scan_results.json` | Latest full scan |

---

## 🎯 Recommended Schedule

**For active traders:**
- Pre-market (8:00 AM): Quick scan
- Market open (9:30 AM): Full scan
- Midday (12:00 PM): Quick scan
- Market close (4:00 PM): Full scan

**For swing traders:**
- Daily morning (7:00 AM): Full scan
- Earnings days: Additional pre-market scan

**For investors:**
- Weekend: Full market analysis
- Weekdays: Only if alerts received

---

## 🔒 Security Notes

1. **Never commit tokens to git**
   ```bash
   echo ".telegram_config" >> .gitignore
   ```

2. **Use environment variables in production**
   ```bash
   # Instead of hardcoding
   export TELEGRAM_BOT_TOKEN=$(cat .telegram_config | grep TOKEN | cut -d= -f2)
   ```

3. **Restrict bot access**
   - Don't share bot token
   - Use group chat with specific members
   - Disable bot if compromised

---

## ✅ Status Checklist

- [ ] Bot created via @BotFather
- [ ] Chat ID obtained from @userinfobot
- [ ] Configuration saved to `.telegram_config`
- [ ] Test message sent successfully
- [ ] First scan completed
- [ ] Scheduled automation configured
- [ ] Alerts received on phone

---

**Your bot is ready! You now have 362 tickers scanned automatically with Telegram alerts.**
