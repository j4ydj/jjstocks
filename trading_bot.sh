#!/bin/bash
# TRADING BOT - One-command automation
# Usage: ./trading_bot.sh [command]

set -e

DIR="/Users/home/stocks"
VENV="$DIR/venv/bin/python"
LOG="$DIR/bot.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

show_help() {
    echo "Trading Bot Automation"
    echo ""
    echo "Commands:"
    echo "  setup       - Configure Telegram bot"
    echo "  test        - Test Telegram connection"
    echo "  quick       - Quick scan (23 tickers, ~2 min)"
    echo "  full        - Full scan (154 tickers, ~7 min)"
    echo "  all         - Complete market scan (362 tickers)"
    echo "  schedule    - Set up automatic daily scans"
    echo "  server      - Run Telegram bot server (respond to commands)"
    echo "  status      - Check bot status"
    echo "  logs        - View recent logs"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  ./trading_bot.sh setup"
    echo "  ./trading_bot.sh quick"
    echo "  ./trading_bot.sh full"
    echo "  ./trading_bot.sh server  <-- Run bot server"
}

check_venv() {
    if [ ! -f "$VENV" ]; then
        echo -e "${RED}Error: Virtual environment not found${NC}"
        echo "Run: python -m venv venv && venv/bin/pip install -r requirements.txt"
        exit 1
    fi
}

cmd_setup() {
    echo -e "${YELLOW}Setting up Telegram bot...${NC}"
    $VENV $DIR/setup_telegram.py
}

cmd_test() {
    echo -e "${YELLOW}Testing Telegram connection...${NC}"
    $VENV $DIR/telegram_alerts.py --test
}

cmd_quick() {
    echo -e "${YELLOW}Running quick scan (23 tickers)...${NC}"
    echo "This will take ~2 minutes"
    echo ""
    $VENV $DIR/auto_runner.py --once --quick 2>&1 | tee -a $LOG
}

cmd_full() {
    echo -e "${YELLOW}Running full scan (154 tickers)...${NC}"
    echo "This will take ~7 minutes"
    echo "Press Ctrl+C to cancel"
    echo ""
    $VENV $DIR/auto_runner.py --once 2>&1 | tee -a $LOG
}

cmd_all() {
    echo -e "${YELLOW}Running complete market scan (362 tickers)...${NC}"
    echo "This will take ~15-20 minutes"
    echo "Press Ctrl+C to cancel"
    echo ""
    $VENV $DIR/market_wide_scanner.py 2>&1 | tee -a $LOG
}

cmd_schedule() {
    echo -e "${YELLOW}Setting up scheduled scans...${NC}"
    echo ""
    echo "Choose schedule:"
    echo "  1) Daily morning (7:00 AM)"
    echo "  2) Market hours (9:30 AM, 12:00 PM)"
    echo "  3) Hourly during market"
    echo "  4) Custom cron"
    echo ""
    read -p "Select (1-4): " choice
    
    case $choice in
        1)
            echo "0 7 * * * cd $DIR && venv/bin/python auto_runner.py --once >> cron.log 2>&1" | crontab -
            echo -e "${GREEN}✓ Daily scans scheduled${NC}"
            ;;
        2)
            (crontab -l 2>/dev/null; echo "30 9 * * 1-5 cd $DIR && venv/bin/python auto_runner.py --once --quick >> cron.log 2>&1") | crontab -
            (crontab -l 2>/dev/null; echo "0 12 * * 1-5 cd $DIR && venv/bin/python auto_runner.py --once --quick >> cron.log 2>&1") | crontab -
            echo -e "${GREEN}✓ Market hours scans scheduled${NC}"
            ;;
        3)
            echo "0 9-16 * * 1-5 cd $DIR && venv/bin/python auto_runner.py --once --quick >> cron.log 2>&1" | crontab -
            echo -e "${GREEN}✓ Hourly scans scheduled${NC}"
            ;;
        4)
            echo "Edit crontab manually: crontab -e"
            echo "Example: 0 9 * * 1-5 cd $DIR && venv/bin/python auto_runner.py --once"
            ;;
    esac
}

cmd_status() {
    echo -e "${YELLOW}Bot Status${NC}"
    echo "=========="
    
    # Check Telegram config
    if [ -f "$DIR/.telegram_config" ]; then
        echo -e "${GREEN}✓ Telegram configured${NC}"
    else
        echo -e "${RED}✗ Telegram not configured${NC}"
    fi
    
    # Check recent scans
    if [ -f "$DIR/auto_runner_state.json" ]; then
        echo -e "${GREEN}✓ State file exists${NC}"
        cat $DIR/auto_runner_state.json
    fi
    
    # Check for recent results
    latest=$(ls -t $DIR/scan_*.json 2>/dev/null | head -1)
    if [ -n "$latest" ]; then
        echo -e "${GREEN}✓ Latest scan: $(basename $latest)${NC}"
    fi
}

cmd_logs() {
    echo -e "${YELLOW}Recent logs:${NC}"
    if [ -f "$LOG" ]; then
        tail -50 $LOG
    else
        echo "No logs found. Run a scan first."
    fi
}

# Main
check_venv

case "${1:-help}" in
    setup)
        cmd_setup
        ;;
    test)
        cmd_test
        ;;
    quick)
        cmd_quick
        ;;
    full)
        cmd_full
        ;;
    all)
        cmd_all
        ;;
    schedule)
        cmd_schedule
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    server)
        echo -e "${YELLOW}Starting Telegram bot server...${NC}"
        echo "Bot will respond to commands in Telegram"
        echo "Press Ctrl+C to stop"
        echo ""
        $VENV $DIR/telegram_bot_server.py
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
