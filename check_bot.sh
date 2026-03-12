#!/bin/bash
# Check if the Simple Trading Bot is running

echo "🔍 CHECKING SIMPLE TRADING BOT STATUS"
echo "==============================="

BOT_PID=$(pgrep -f "simple_trading_bot.py" | head -n 1)

if [ -n "$BOT_PID" ] && ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "✅ Bot is RUNNING (PID: $BOT_PID)"

    if [ -f "simple_bot.log" ]; then
        echo ""
        echo "📋 Recent activity (last 10 lines):"
        echo "-----------------------------------"
        tail -10 simple_bot.log | sed -E 's#bot[0-9]+:[A-Za-z0-9_-]+#bot<redacted>#g'
    fi

    echo ""
    echo "📱 Your bot is accessible via Telegram!"
    echo "💬 Search for your bot and send /start"
else
    echo "❌ Bot is NOT running"
    echo "🚀 Run ./start_simple.sh to start the bot"
fi

echo ""
echo "📊 System resources:"
if [ -n "$BOT_PID" ] && ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "Memory usage: $(ps -o %mem= -p "$BOT_PID" 2>/dev/null | awk 'NR==1 {print $1"%"}' || echo "N/A")"
    echo "Uptime: $(ps -o etime= -p "$BOT_PID" 2>/dev/null | awk 'NR==1 {print $1}' || echo "N/A")"
else
    echo "Memory usage: N/A"
    echo "Uptime: N/A"
fi