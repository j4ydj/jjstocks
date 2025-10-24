#!/bin/bash
# Check if the Trading Telegram Bot is running

echo "🔍 CHECKING TELEGRAM BOT STATUS"
echo "==============================="

# Check if PID file exists
if [ -f "bot.pid" ]; then
    BOT_PID=$(cat bot.pid)
    
    # Check if process is actually running
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "✅ Bot is RUNNING (PID: $BOT_PID)"
        
        # Show recent logs
        if [ -f "bot_output.log" ]; then
            echo ""
            echo "📋 Recent activity (last 10 lines):"
            echo "-----------------------------------"
            tail -10 bot_output.log
        fi
        
        echo ""
        echo "📱 Your bot is accessible via Telegram!"
        echo "💬 Search for your bot and send /start"
        
    else
        echo "❌ Bot is NOT running (stale PID file)"
        rm -f bot.pid
        echo "🔄 Run ./start_bot.sh to restart"
    fi
else
    echo "❌ Bot is NOT running (no PID file)"
    echo "🚀 Run ./start_bot.sh to start the bot"
fi

echo ""
echo "📊 System resources:"
echo "Memory usage: $(ps -o pid,ppid,cmd,%mem --pid $BOT_PID 2>/dev/null | tail -1 | awk '{print $4"%"}' || echo "N/A")"
echo "Uptime: $(ps -o pid,etime --pid $BOT_PID 2>/dev/null | tail -1 | awk '{print $2}' || echo "N/A")"