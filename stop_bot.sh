#!/bin/bash
# Stop the Trading Telegram Bot

echo "🛑 STOPPING TELEGRAM BOT"
echo "========================="

# Check if PID file exists
if [ -f "bot.pid" ]; then
    BOT_PID=$(cat bot.pid)
    
    # Check if process is running and kill it
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "🔄 Stopping bot (PID: $BOT_PID)..."
        kill $BOT_PID
        
        # Wait a moment and check if it's stopped
        sleep 2
        if ps -p $BOT_PID > /dev/null 2>&1; then
            echo "⚠️  Bot didn't stop gracefully, forcing termination..."
            kill -9 $BOT_PID
        fi
        
        echo "✅ Bot stopped successfully"
    else
        echo "ℹ️  Bot was not running"
    fi
    
    # Clean up PID file
    rm -f bot.pid
else
    echo "ℹ️  No bot PID file found"
fi

# Kill any remaining bot processes
REMAINING=$(pgrep -f "trading_telegram_bot.py" | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo "🔄 Killing $REMAINING remaining bot processes..."
    pkill -f "trading_telegram_bot.py"
    echo "✅ All bot processes terminated"
fi

echo ""
echo "📋 Bot management commands:"
echo "• Start bot: ./start_bot.sh"
echo "• Check status: ./check_bot.sh"
echo "• View logs: tail -f bot_output.log"