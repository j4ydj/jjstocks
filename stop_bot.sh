#!/bin/bash
# Stop the Simple Trading Bot

echo "🛑 STOPPING SIMPLE TRADING BOT"
echo "========================="

BOT_PID=$(pgrep -f "simple_trading_bot.py" | head -n 1)

if [ -n "$BOT_PID" ] && ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "🔄 Stopping bot (PID: $BOT_PID)..."
    kill "$BOT_PID"

    sleep 2
    if ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo "⚠️  Bot didn't stop gracefully, forcing termination..."
        kill -9 "$BOT_PID"
    fi

    echo "✅ Bot stopped successfully"
else
    echo "ℹ️  Bot is not currently running"
fi

# Kill any remaining bot processes
REMAINING=$(pgrep -f "simple_trading_bot.py" | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo "🔄 Killing $REMAINING remaining bot processes..."
    pkill -f "simple_trading_bot.py"
    echo "✅ All bot processes terminated"
fi

echo ""
echo "📋 Bot management commands:"
echo "• Start bot: ./start_simple.sh"
echo "• Check status: ./check_bot.sh"
echo "• View logs: tail -f simple_bot.log"