#!/usr/bin/env python3
"""
Simple Trading Bot - Stripped Back to Basics
A clean, working Telegram bot for stock analysis
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# David strategy import
try:
    from david_portfolio_strategy import scan_david_opportunities
    DAVID_AVAILABLE = True
except ImportError:
    DAVID_AVAILABLE = False
    logger.warning("David strategy not available")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load config
def load_config():
    """Load configuration"""
    try:
        with open('trading_config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Config error: {e}")
        return {
            'TELEGRAM_BOT_TOKEN': '',
            'TELEGRAM_CHAT_ID': '',
            'WATCHLIST': ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL']
        }

config = load_config()

# ============================================================================
# SIMPLE STOCK ANALYSIS
# ============================================================================

def get_stock_data(ticker: str, days: int = 90):
    """Get stock data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=f"{days}d")
        if df.empty:
            return None
        return df
    except Exception as e:
        logger.error(f"Error getting {ticker}: {e}")
        return None

def calculate_rsi(df, period=14):
    """Calculate RSI indicator"""
    try:
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50

def calculate_macd(df):
    """Calculate MACD"""
    try:
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd.iloc[-1], signal.iloc[-1]
    except:
        return 0, 0

def get_simple_signal(ticker: str):
    """Get a simple trading signal"""
    try:
        df = get_stock_data(ticker)
        if df is None or len(df) < 30:
            return None
        
        # Current price
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        # Moving averages
        sma_20 = df['Close'].rolling(window=20).mean().iloc[-1]
        sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
        
        # RSI
        rsi = calculate_rsi(df)
        
        # MACD
        macd, signal = calculate_macd(df)
        
        # Simple signal logic
        signal_score = 0
        reasons = []
        
        # Price vs moving averages
        if current_price > sma_20 and current_price > sma_50:
            signal_score += 1
            reasons.append("Price above MAs")
        elif current_price < sma_20 and current_price < sma_50:
            signal_score -= 1
            reasons.append("Price below MAs")
        
        # Golden/Death cross
        if sma_20 > sma_50:
            signal_score += 1
            reasons.append("Golden cross (20>50)")
        else:
            signal_score -= 1
            reasons.append("Death cross (20<50)")
        
        # RSI
        if rsi < 30:
            signal_score += 2
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            signal_score -= 2
            reasons.append(f"RSI overbought ({rsi:.1f})")
        
        # MACD
        if macd > signal:
            signal_score += 1
            reasons.append("MACD bullish")
        else:
            signal_score -= 1
            reasons.append("MACD bearish")
        
        # Determine signal
        if signal_score >= 2:
            signal_type = "🟢 BUY"
        elif signal_score <= -2:
            signal_type = "🔴 SELL"
        else:
            signal_type = "⚪ HOLD"
        
        return {
            'ticker': ticker,
            'price': current_price,
            'change_pct': change_pct,
            'signal': signal_type,
            'signal_score': signal_score,
            'rsi': rsi,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'macd': macd,
            'macd_signal': signal,
            'reasons': reasons
        }
        
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}")
        return None

# ============================================================================
# TELEGRAM BOT HANDLERS
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    keyboard = [
        [InlineKeyboardButton("📊 Analyze Stock", callback_data='analyze')],
        [InlineKeyboardButton("📋 Watchlist", callback_data='watchlist')],
        [InlineKeyboardButton("🔍 Quick Scan", callback_data='scan')],
    ]
    
    # Add David strategy if available
    if DAVID_AVAILABLE:
        keyboard.append([InlineKeyboardButton("🎯 Small-Cap Opportunities (David)", callback_data='david')])
    
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data='help')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """
🤖 **Simple Trading Bot**

I help you analyze stocks with basic technical indicators.

Choose an option below or use these commands:
• /analyze TICKER - Analyze any stock
• /watchlist - View your watchlist
• /scan - Quick scan of watchlist"""
    
    if DAVID_AVAILABLE:
        welcome_text += "\n• /david - Find small-cap opportunities"
    
    welcome_text += "\n• /help - Show help\n\nKeep it simple! 📈"
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze command"""
    if not context.args:
        await update.message.reply_text("Usage: /analyze TICKER\nExample: /analyze AAPL")
        return
    
    ticker = context.args[0].upper()
    await update.message.reply_text(f"🔍 Analyzing {ticker}...")
    
    result = get_simple_signal(ticker)
    
    if not result:
        await update.message.reply_text(f"❌ Could not analyze {ticker}. Check the ticker and try again.")
        return
    
    # Format the response
    response = f"""
📊 **{result['ticker']} Analysis**

💰 Price: ${result['price']:.2f} ({result['change_pct']:+.2f}%)

**Technical Indicators:**
• RSI: {result['rsi']:.1f}
• SMA 20: ${result['sma_20']:.2f}
• SMA 50: ${result['sma_50']:.2f}
• MACD: {result['macd']:.2f}
• Signal: {result['macd_signal']:.2f}

**Signal:** {result['signal']} (Score: {result['signal_score']})

**Reasoning:**
"""
    
    for reason in result['reasons']:
        response += f"• {reason}\n"
    
    response += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def watchlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watchlist command"""
    watchlist = config.get('WATCHLIST', ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL'])
    
    response = "📋 **Your Watchlist:**\n\n"
    
    for ticker in watchlist[:10]:  # Limit to 10
        try:
            stock = yf.Ticker(ticker)
            info = stock.history(period='1d')
            if not info.empty:
                price = info['Close'].iloc[-1]
                response += f"• {ticker}: ${price:.2f}\n"
            else:
                response += f"• {ticker}: (no data)\n"
        except:
            response += f"• {ticker}: (error)\n"
    
    response += f"\n💡 Use /analyze TICKER to get details"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command"""
    await update.message.reply_text("🔍 Scanning watchlist...")
    
    watchlist = config.get('WATCHLIST', ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL'])
    signals = []
    
    for ticker in watchlist[:10]:  # Limit to 10
        result = get_simple_signal(ticker)
        if result and result['signal'] != "⚪ HOLD":
            signals.append(result)
    
    if not signals:
        await update.message.reply_text("✅ No strong signals found. Market looks neutral.")
        return
    
    response = f"📊 **Scan Results** ({len(signals)} signals)\n\n"
    
    for result in signals:
        response += f"{result['signal']} **{result['ticker']}** ${result['price']:.2f}\n"
        response += f"  Score: {result['signal_score']}, RSI: {result['rsi']:.1f}\n\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def david_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /david command - Small-cap opportunities"""
    if not DAVID_AVAILABLE:
        await update.message.reply_text("❌ David strategy not available. Install required packages.")
        return
    
    await update.message.reply_text("🎯 Scanning for small-cap opportunities...\n⏱️ This may take 30-60 seconds...")
    
    try:
        # Run the David strategy scan
        report = await scan_david_opportunities()
        
        # Split report if too long (Telegram limit is 4096 chars)
        if len(report) > 4000:
            parts = [report[i:i+3900] for i in range(0, len(report), 3900)]
            for i, part in enumerate(parts, 1):
                await update.message.reply_text(f"📊 Part {i}/{len(parts)}:\n\n{part}")
        else:
            await update.message.reply_text(report)
            
    except Exception as e:
        logger.error(f"David strategy error: {e}")
        await update.message.reply_text(f"❌ Error running David strategy: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
ℹ️ **Simple Trading Bot Help**

**Commands:**
• /start - Show main menu
• /analyze TICKER - Analyze any stock
• /watchlist - View your watchlist
• /scan - Scan watchlist for signals"""
    
    if DAVID_AVAILABLE:
        help_text += "\n• /david - Find small-cap opportunities (David vs Goliath)"
    
    help_text += """
• /help - Show this help

**How it works:**
The bot uses simple technical analysis:
• Moving averages (20 & 50 day)
• RSI (Relative Strength Index)
• MACD (Moving Average Convergence Divergence)

**Signals:**
🟢 BUY - Bullish indicators
🔴 SELL - Bearish indicators
⚪ HOLD - Neutral

**Example:**
/analyze AAPL

Simple and reliable! 📈
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'analyze':
        await query.message.reply_text("Type: /analyze TICKER\nExample: /analyze AAPL")
    elif query.data == 'watchlist':
        await watchlist_command(update, context)
    elif query.data == 'scan':
        await scan_command(update, context)
    elif query.data == 'david':
        if DAVID_AVAILABLE:
            # Create a fake update for david_command
            await query.message.reply_text("🎯 Starting David vs Goliath scan...")
            await david_command(update, context)
        else:
            await query.message.reply_text("❌ David strategy not available")
    elif query.data == 'help':
        await help_command(update, context)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages"""
    text = update.message.text.upper()
    
    # Check if it looks like a ticker (2-5 capital letters)
    if len(text) >= 2 and len(text) <= 5 and text.isalpha():
        await update.message.reply_text(f"🔍 Analyzing {text}...")
        result = get_simple_signal(text)
        
        if result:
            response = f"""
📊 **{result['ticker']}**
💰 ${result['price']:.2f} ({result['change_pct']:+.2f}%)
{result['signal']}
RSI: {result['rsi']:.1f}

Use /analyze {text} for full details
"""
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Could not analyze {text}")
    else:
        await update.message.reply_text("💡 Send a ticker symbol (e.g., AAPL) or use /help")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the bot"""
    print("🤖 Simple Trading Bot Starting...")
    
    # Check config
    bot_token = config.get('TELEGRAM_BOT_TOKEN')
    if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
        print("❌ Error: TELEGRAM_BOT_TOKEN not configured in trading_config.json")
        return
    
    print("✅ Configuration loaded")
    print(f"📋 Watchlist: {', '.join(config.get('WATCHLIST', [])[:5])}")
    
    # Create application
    try:
        application = Application.builder().token(bot_token).build()
        print("✅ Bot initialized")
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("analyze", analyze_command))
        application.add_handler(CommandHandler("watchlist", watchlist_command))
        application.add_handler(CommandHandler("scan", scan_command))
        application.add_handler(CommandHandler("help", help_command))
        
        # Add David strategy if available
        if DAVID_AVAILABLE:
            application.add_handler(CommandHandler("david", david_command))
            print("✅ David vs Goliath strategy loaded")
        
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print("✅ Handlers registered")
        print("\n🚀 Bot is running!")
        print("📱 Open Telegram and send /start to your bot")
        print("⏹️  Press Ctrl+C to stop\n")
        
        # Start polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Bot error: {e}")

if __name__ == "__main__":
    main()

