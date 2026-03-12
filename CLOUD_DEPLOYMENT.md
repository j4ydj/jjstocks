# ☁️ CLOUD DEPLOYMENT GUIDES

Deploy your trading bot to the cloud so it runs 24/7 without your computer.

---

## 🎯 Recommended: Railway (Easiest)

**Best for:** Beginners, free tier, simple deployment

### 1. Sign Up
- Go to [railway.app](https://railway.app)
- Sign up with GitHub
- No credit card required for free tier

### 2. Create Project
```bash
# In your project directory
cd /Users/home/stocks

# Initialize git (if not already)
git init
git add .
git commit -m "Trading bot ready for cloud"

# Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git
git push -u origin main
```

### 3. Deploy to Railway
- Railway dashboard → New Project → Deploy from GitHub repo
- Select your repo
- Add environment variables:
  ```
  TELEGRAM_BOT_TOKEN=8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8
  TELEGRAM_CHAT_ID=YOUR_CHAT_ID
  ```
- Railway auto-detects Python and installs requirements
- Bot starts automatically

### 4. Set Schedule (Cron)
In Railway dashboard:
- Go to your service
- Click "Settings" → "Cron"
- Add: `0 9,12 * * 1-5` (9 AM and 12 PM, Mon-Fri)
- This runs `python cloud_run.py` on schedule

**Cost:** FREE (500 hours/month)

---

## 🔥 Alternative: AWS Lambda (Most Robust)

**Best for:** Production, scheduled triggers, very cheap

### 1. Setup AWS Account
- Sign up at [aws.amazon.com](https://aws.amazon.com)
- Requires credit card but Lambda has generous free tier (1M requests/month)

### 2. Create Lambda Function
Create `lambda_function.py`:
```python
import json
import os

def lambda_handler(event, context):
    # Import and run your bot
    import sys
    sys.path.insert(0, '/var/task')
    
    from working_edge_system import WorkingEdgeSystem
    from telegram_alerts import TelegramBot
    
    # Run quick scan
    system = WorkingEdgeSystem()
    universe = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
                "GME", "AMC", "PLTR", "COIN", "HOOD", "SPY", "QQQ",
                "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU", "RKLB"]
    
    signals = system.scan(universe, min_score=2)
    
    # Send to Telegram
    bot = TelegramBot()
    if signals:
        bot.send_daily_summary(signals, len(universe))
        longs = [s for s in signals if s.direction == "LONG"][:5]
        if longs:
            bot.send_message("🎯 <b>Top Picks</b>")
            for s in longs:
                bot.send_signal_alert({
                    'ticker': s.ticker,
                    'score': s.score,
                    'direction': s.direction,
                    'confidence': s.confidence,
                    'sources': s.sources,
                    'catalyst': s.catalyst
                })
    
    return {
        'statusCode': 200,
        'body': json.dumps(f'Scanned {len(universe)} tickers, found {len(signals)} signals')
    }
```

Create `requirements.txt`:
```
yfinance>=0.2.28
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
```

### 3. Deploy via AWS Console
- Go to AWS Lambda
- Create function → Python 3.11
- Upload code as ZIP
- Set environment variables
- Set timeout: 5 minutes
- Set memory: 512 MB

### 4. Schedule with CloudWatch
- Go to CloudWatch → Rules → Create Rule
- Schedule: `cron(30 9 ? * MON-FRI *)` (9:30 AM ET)
- Target: Your Lambda function
- Add another rule for 12 PM

### 5. Test
- Click "Test" in Lambda console
- Check Telegram for message

**Cost:** ~$0.20/month (free tier covers most usage)

---

## 🌐 Alternative: Google Cloud Functions

**Best for:** Google ecosystem users, similar to Lambda

### 1. Setup
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID
```

### 2. Deploy
```bash
# Create function
gcloud functions deploy trading_bot \
  --runtime python311 \
  --trigger-http \
  --entry-point run_scan \
  --memory 512MB \
  --timeout 300s \
  --set-env-vars TELEGRAM_BOT_TOKEN=8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8,TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

### 3. Schedule with Cloud Scheduler
```bash
gcloud scheduler jobs create http trading-bot-morning \
  --schedule="30 9 * * 1-5" \
  --uri="https://REGION-PROJECT_ID.cloudfunctions.net/trading_bot" \
  --http-method=POST
```

**Cost:** ~$0.10/month (2M free invocations/month)

---

## 🟣 Alternative: Heroku (Classic)

**Best for:** Simple, well-documented, free tier (sleeps after 30 min idle)

### 1. Setup
```bash
# Install Heroku CLI
brew tap heroku/brew && brew install heroku

# Login
heroku login

# Create app
cd /Users/home/stocks
heroku create trading-bot-app
```

### 2. Configure
Create `Procfile`:
```
worker: python cloud_worker.py
```

Create `cloud_worker.py`:
```python
#!/usr/bin/env python3
"""Cloud worker for Heroku/Railway"""
import os
import time
from datetime import datetime

# Run continuous loop
while True:
    now = datetime.now()
    
    # Check if market hours (9:30 AM - 4 PM, Mon-Fri)
    if now.weekday() < 5 and (9 <= now.hour < 16):
        print(f"[{now}] Running scan...")
        
        # Import here to refresh modules
        from working_edge_system import WorkingEdgeSystem
        from telegram_alerts import TelegramBot
        
        system = WorkingEdgeSystem()
        universe = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
                   "GME", "AMC", "PLTR", "COIN", "HOOD", "SPY", "QQQ",
                   "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU"]
        
        signals = system.scan(universe, min_score=2)
        
        bot = TelegramBot()
        if signals:
            bot.send_daily_summary(signals, len(universe))
            print(f"Sent {len(signals)} signals")
        else:
            print("No signals found")
    
    # Sleep 1 hour
    time.sleep(3600)
```

### 3. Deploy
```bash
git push heroku main

# Scale worker
heroku ps:scale worker=1

# Set config
heroku config:set TELEGRAM_BOT_TOKEN=8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8
heroku config:set TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

**Note:** Free tier sleeps after 30 min. Use paid tier ($7/month) for 24/7.

---

## 📦 Deployment Files Created

| File | Purpose |
|------|---------|
| `cloud_run.py` | Entry point for scheduled cloud runs |
| `lambda_function.py` | AWS Lambda handler |
| `cloud_worker.py` | Continuous worker for Heroku/Railway |
| `requirements.txt` | Dependencies for cloud |
| `railway.json` | Railway configuration |
| `Procfile` | Heroku process definition |

---

## 🚀 Quick Deploy: Railway (Recommended)

### Step 1: Prepare
```bash
cd /Users/home/stocks

# Create requirements.txt if not exists
cat > requirements.txt << EOF
yfinance>=0.2.28
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
pytrends>=4.9.0
EOF

# Create cloud entry point
cat > cloud_run.py << 'EOF'
#!/usr/bin/env python3
"""Cloud entry point for scheduled runs"""
import os
from working_edge_system import WorkingEdgeSystem
from telegram_alerts import TelegramBot

def run():
    print("Starting cloud scan...")
    
    system = WorkingEdgeSystem()
    universe = [
        "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL",
        "GME", "AMC", "PLTR", "COIN", "HOOD", "SPY", "QQQ",
        "AMD", "NFLX", "CRM", "UBER", "SNOW", "ROKU"
    ]
    
    signals = system.scan(universe, min_score=2)
    
    bot = TelegramBot()
    if bot.enabled and signals:
        bot.send_daily_summary(signals, len(universe))
        longs = [s for s in signals if s.direction == "LONG"][:5]
        if longs:
            bot.send_message("🎯 <b>Top Picks</b>")
            for s in longs:
                bot.send_signal_alert({
                    'ticker': s.ticker,
                    'score': s.score,
                    'direction': s.direction,
                    'confidence': s.confidence,
                    'sources': s.sources,
                    'catalyst': s.catalyst
                })
        print(f"Sent {len(signals)} signals to Telegram")
    else:
        print(f"Found {len(signals)} signals (Telegram not configured)")
    
    return len(signals)

if __name__ == "__main__":
    run()
EOF
```

### Step 2: Push to GitHub
```bash
git add .
git commit -m "Ready for cloud deployment"
git push origin main
```

### Step 3: Deploy to Railway
1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Select your repo
4. Add environment variables in Railway dashboard
5. Bot deploys automatically

### Step 4: Schedule
In Railway dashboard:
- Service → Settings
- Cron → `0 9,12 * * 1-5`
- (9:30 AM and 12 PM, Monday-Friday)

---

## 💰 Cost Comparison

| Service | Free Tier | Paid Cost | Best For |
|---------|-----------|-----------|----------|
| **Railway** | 500 hrs/mo | $5/mo | Beginners |
| **AWS Lambda** | 1M requests | $0.20/mo | Production |
| **Google Cloud** | 2M requests | $0.10/mo | Google users |
| **Heroku** | 1000 hrs/mo (sleeps) | $7/mo | Simple apps |

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Cloud account created (Railway/AWS/GCP/Heroku)
- [ ] Environment variables set (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
- [ ] Service deployed successfully
- [ ] Schedule configured (cron)
- [ ] Test run completed
- [ ] Telegram alert received
- [ ] Local computer can be shut off

---

## 🎯 After Deployment

Once deployed to cloud:

1. **Your computer can be off** - bot runs in cloud
2. **You'll get Telegram alerts** - on your phone anywhere
3. **Scans run automatically** - on your schedule
4. **No maintenance needed** - cloud handles everything

**You literally just wait for Telegram alerts.**

---

## 📱 Your Workflow After Cloud Deploy

1. **Wake up** → Check Telegram for morning scan
2. **Go about your day** → Bot runs in cloud
3. **Midday** → Telegram alert with midday scan
4. **Make decisions** → Based on signals in your phone

**Zero interaction with servers needed.**

---

## 🆘 Need Help?

**Railway (Easiest):**
- Join [Railway Discord](https://discord.gg/railway)
- Very helpful community

**AWS Lambda:**
- [AWS Lambda Docs](https://docs.aws.amazon.com/lambda/)
- Serverless Stack tutorials

**Google Cloud:**
- [Cloud Functions Docs](https://cloud.google.com/functions/docs)

---

## 🚀 Start Now

**Easiest path (5 minutes):**

1. Sign up at [railway.app](https://railway.app)
2. Connect GitHub repo
3. Add your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
4. Deploy
5. Set schedule: `0 9,12 * * 1-5`

**Done. Your bot now runs in the cloud 24/7.**
