#!/bin/bash
# PREPARE FOR CLOUD DEPLOYMENT
# =============================

set -e

echo "☁️  Preparing Trading Bot for Cloud Deployment"
echo "================================================"
echo ""

# Check if in git repo
if [ ! -d .git ]; then
    echo "Initializing git repository..."
    git init
fi

# Check files exist
echo "Checking required files..."
required_files=(
    "cloud_run.py"
    "requirements.txt"
    "railway.json"
    "working_edge_system.py"
    "telegram_alerts.py"
    "prediction_markets.py"
    "wikipedia_views.py"
    "sec_filing_risk.py"
    "retail_sentiment_edge.py"
    "sentiment_intelligence.py"
    "earnings_drift.py"
    "run_winning_strategy.py"
    "backtest.py"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file MISSING"
    fi
done

echo ""
echo "Checking .gitignore..."
if [ ! -f .gitignore ]; then
cat > .gitignore << 'EOF'
# Environment variables
.env
.telegram_config

# Logs
*.log
bot.log
bot_server.log
telegram_bot_server.log
auto_runner.log

# Runtime files
*.pid
nohup.out

# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/

# Scans (keep last few)
scan_*.json
market_scan_results.json
signals.json
edge_roadmap.json

# State
auto_runner_state.json
EOF
    echo "  ✓ Created .gitignore"
else
    echo "  ✓ .gitignore exists"
fi

# Commit everything
echo ""
echo "Committing to git..."
git add -A
git commit -m "Trading bot ready for cloud deployment" || echo "Nothing new to commit"

echo ""
echo "================================================"
echo "✅ PREPARED FOR CLOUD DEPLOYMENT"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Push to GitHub:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git"
echo "   git push -u origin main"
echo ""
echo "2. Deploy to Railway (easiest):"
echo "   - Go to https://railway.app"
echo "   - Sign up with GitHub"
echo "   - New Project → Deploy from GitHub"
echo "   - Select this repo"
echo "   - Add environment variables:"
echo "     TELEGRAM_BOT_TOKEN=8243624386:AAEjeDKQg4k3XIX2lM_3qkkpcr9HDCQWJw8"
echo "     TELEGRAM_CHAT_ID=YOUR_CHAT_ID"
echo ""
echo "3. Set schedule in Railway dashboard:"
echo "   - Service → Settings → Cron"
echo "   - Schedule: 0 9,12 * * 1-5"
echo "   - (9 AM and 12 PM, Monday-Friday)"
echo ""
echo "Bot will then run in cloud 24/7!"
echo ""
