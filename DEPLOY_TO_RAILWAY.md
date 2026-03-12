# 🚀 Deploy to Railway (Step-by-Step)

## Prerequisites
1. GitHub account
2. Railway account (free)
3. Your code committed to git ✅ (Done)

---

## Step 1: Push to GitHub

### Option A: Using GitHub Desktop (Easiest for macOS)
1. Download [GitHub Desktop](https://desktop.github.com)
2. Open it, sign in with your GitHub account
3. Add local repository → Select `/Users/home/stocks`
4. Click "Publish repository"
5. Make it **public** (Railway requires public repos for free tier)
6. Click "Publish repository"

### Option B: Using Git Command Line
```bash
# Create GitHub repo first:
# 1. Go to https://github.com/new
# 2. Name it "trading-bot"
# 3. Make it PUBLIC
# 4. Don't initialize with README

# Then run these commands:
cd /Users/home/stocks
git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git
git branch -M main
git push -u origin main
```

---

## Step 2: Sign Up for Railway

1. Go to [railway.app](https://railway.app)
2. Click "Start for Free"
3. Sign up with your **GitHub account**
4. Authorize Railway to access your repos

---

## Step 3: Deploy from GitHub

1. In Railway dashboard, click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose your `trading-bot` repository
4. Railway will auto-detect it's a Python project
5. Click **"Deploy"**

---

## Step 4: Add Environment Variables

In Railway dashboard:
1. Click on your deployed service
2. Go to **"Variables"** tab
3. Click **"New Variable"**
4. Add these two variables:

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | `8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8` |
| `TELEGRAM_CHAT_ID` | `YOUR_CHAT_ID_HERE` |

**To get your Chat ID:**
1. Open Telegram
2. Message @userinfobot
3. Copy the number (looks like `123456789`)
4. Paste it as `TELEGRAM_CHAT_ID`

---

## Step 5: Set Schedule (Cron Job)

Railway will run the bot on a schedule:

1. In Railway, go to your service
2. Click **"Settings"**
3. Scroll to **"Cron Jobs"**
4. Click **"Add Cron Job"**
5. Set:
   - **Command:** `python cloud_run.py`
   - **Schedule:** `0 9,12 * * 1-5`
6. Click **"Add"**

This runs at 9 AM and 12 PM (noon), Monday-Friday.

---

## Step 6: Test Deploy

1. In Railway, click **"Deployments"**
2. Wait for "Success" status
3. Click **"Logs"** to see output
4. You should see:
   ```
   CLOUD SCAN STARTED
   Scanning 21 tickers...
   Telegram alerts sent successfully
   ```

5. Check Telegram for test message!

---

## Step 7: Done! 🎉

Your bot now runs in the cloud:
- ✅ Scans automatically 2x per day
- ✅ Sends alerts to your phone
- ✅ Runs 24/7 without your computer
- ✅ No maintenance needed

---

## Troubleshooting

### Issue: "Repository not found"
**Fix:** Make your GitHub repo PUBLIC

### Issue: "Telegram not configured"
**Fix:** Double-check your env variables in Railway dashboard

### Issue: Bot not sending messages
**Fix:** 
1. Make sure you messaged @userinfobot to get your chat ID
2. Make sure you started a conversation with your bot in Telegram
3. Check Railway logs for errors

### Issue: Schedule not running
**Fix:**
1. Check that cron syntax is correct: `0 9,12 * * 1-5`
2. Verify command is: `python cloud_run.py`
3. Check Railway logs for any errors

---

## Alternative Schedule Options

| Schedule | Cron Expression | Description |
|----------|----------------|-------------|
| Every hour market hours | `0 9-16 * * 1-5` | 9 AM - 4 PM |
| Morning only | `0 9 * * 1-5` | Just 9 AM |
| 4x per day | `0 9,11,13,15 * * 1-5` | 9, 11, 1, 3 PM |
| Every 30 min | `*/30 9-16 * * 1-5` | 9:00, 9:30, 10:00... |

---

## Railway Dashboard URL
https://railway.app/dashboard

---

## Need Help?

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway (very helpful)
- Or check the logs in Railway dashboard!

---

## 🎯 After Deploy

1. **Close your computer** - bot runs in cloud
2. **Wait for 9 AM** - get first Telegram alert
3. **Trade on signals** - all info in your phone
4. **Check noon** - midday update

**You literally just wait for Telegram alerts.**
