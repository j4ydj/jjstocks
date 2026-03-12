#!/bin/bash
# DEPLOY TO RAILWAY
# =================

set -e

echo "🚀 Railway Deployment Helper"
echo "============================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if command -v railway &> /dev/null; then
    echo "${GREEN}✓ Railway CLI found${NC}"
    USE_CLI=true
else
    echo "${YELLOW}⚠ Railway CLI not installed${NC}"
    USE_CLI=false
fi

# Check if GitHub CLI is installed
if command -v gh &> /dev/null; then
    echo "${GREEN}✓ GitHub CLI found${NC}"
    HAS_GH=true
else
    echo "${YELLOW}⚠ GitHub CLI not installed${NC}"
    HAS_GH=false
fi

echo ""
echo "📋 Prerequisites Check:"
echo "------------------------"

# Check git remote
if git remote -v > /dev/null 2>&1; then
    echo "${GREEN}✓ Git remote configured${NC}"
    REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
    if [ -n "$REMOTE_URL" ]; then
        echo "  URL: $REMOTE_URL"
    fi
else
    echo "${YELLOW}⚠ No Git remote configured${NC}"
    echo "  You'll need to push to GitHub first"
fi

echo ""
echo "${BLUE}🔧 Deployment Options:${NC}"
echo "---------------------"

if [ "$USE_CLI" = true ]; then
    echo "1. Deploy via Railway CLI (fastest)"
    echo "2. Deploy via Railway Dashboard (browser)"
else
    echo "1. Deploy via Railway Dashboard (browser) - RECOMMENDED"
fi

echo ""
echo "${BLUE}📖 Manual Steps:${NC}"
echo "----------------"

if [ "$HAS_GH" = false ]; then
    echo ""
    echo "${YELLOW}Step 1: Push to GitHub${NC}"
    echo "------------------------"
    echo "Option A: Use GitHub Desktop"
    echo "  1. Download: https://desktop.github.com"
    echo "  2. Add local repo: /Users/home/stocks"
    echo "  3. Click 'Publish repository' (make it PUBLIC)"
    echo ""
    echo "Option B: Manual Git commands"
    echo "  1. Go to https://github.com/new"
    echo "  2. Create repo 'trading-bot' (PUBLIC)"
    echo "  3. Run these commands:"
    echo ""
    echo "     git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git"
    echo "     git push -u origin main"
fi

echo ""
echo "${YELLOW}Step 2: Deploy to Railway${NC}"
echo "-------------------------"
echo "  1. Go to https://railway.app"
echo "  2. Sign up with GitHub"
echo "  3. Click 'New Project'"
echo "  4. Select 'Deploy from GitHub repo'"
echo "  5. Choose 'trading-bot' repository"
echo ""

echo "${YELLOW}Step 3: Verify Environment Variables${NC}"
echo "-------------------------------------"
echo "Railway will auto-load these from railway.json:"
echo "  TELEGRAM_BOT_TOKEN: 8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8"
echo "  TELEGRAM_CHAT_ID: 6104130187"
echo ""

echo "${YELLOW}Step 4: Set Schedule${NC}"
echo "--------------------"
echo "In Railway dashboard:"
echo "  Service → Settings → Cron Jobs"
echo "  Command: python cloud_run.py"
echo "  Schedule: 0 9,12 * * 1-5"
echo "  (9 AM and 12 PM, Monday-Friday)"
echo ""

echo "${YELLOW}Step 5: Test${NC}"
echo "------------"
echo "  1. Check Railway logs for 'Telegram alerts sent successfully'"
echo "  2. Check your Telegram for alert"
echo ""

echo "${GREEN}🎉 After Deploy:${NC}"
echo "----------------"
echo "  ✓ Bot runs 24/7 in cloud"
echo "  ✓ Your computer can be OFF"
echo "  ✓ Alerts come to your phone"
echo "  ✓ Runs 9 AM and 12 PM daily"
echo ""

# If Railway CLI is installed, offer to deploy
if [ "$USE_CLI" = true ]; then
    echo "${BLUE}Railway CLI detected!${NC}"
    echo "Would you like to deploy now? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Deploying to Railway..."
        railway login
        railway link
        railway up
        echo "${GREEN}✓ Deployed!${NC}"
        echo "Set up schedule in Railway dashboard:"
        echo "  Command: python cloud_run.py"
        echo "  Schedule: 0 9,12 * * 1-5"
    fi
fi

echo ""
echo "📚 Full guide: DEPLOY_TO_RAILWAY.md"
