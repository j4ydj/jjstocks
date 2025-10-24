#!/bin/bash
# Simple Trading Bot Startup Script

echo "🤖 Simple Trading Bot Launcher"
echo "=============================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade requirements
echo "📥 Installing requirements..."
pip install -q --upgrade pip
pip install -q -r simple_requirements.txt

# Check for config
if [ ! -f "trading_config.json" ]; then
    echo "❌ trading_config.json not found!"
    echo "💡 Please create it with your Telegram bot token"
    exit 1
fi

# Run the bot
echo ""
echo "🚀 Starting bot..."
echo ""
python3 simple_trading_bot.py

