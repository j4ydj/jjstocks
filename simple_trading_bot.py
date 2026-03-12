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

# Setup logging before optional imports so fallback warnings are safe
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

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

# Strategy imports
try:
    from david_portfolio_strategy import scan_david_opportunities
    DAVID_AVAILABLE = True
except ImportError:
    DAVID_AVAILABLE = False
    logger.warning("David strategy not available")

try:
    from sentiment_intelligence import get_sentiment_signal
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    logger.warning("Sentiment intelligence not available")

try:
    from momentum_intelligence import get_momentum_signal
    MOMENTUM_AVAILABLE = True
except ImportError:
    MOMENTUM_AVAILABLE = False
    logger.warning("Momentum intelligence not available")

try:
    from trade_tracker import get_tracker, log_approved_trade, get_performance_report
    TRADE_TRACKER_AVAILABLE = True
except ImportError:
    TRADE_TRACKER_AVAILABLE = False
    logger.warning("Trade tracker not available")

try:
    from insider_intelligence import get_insider_signal
    INSIDER_AVAILABLE = True
except ImportError:
    INSIDER_AVAILABLE = False
    logger.warning("Insider intelligence not available")

try:
    from alternative_data import get_alternative_data_signal
    ALTERNATIVE_DATA_AVAILABLE = True
except ImportError:
    ALTERNATIVE_DATA_AVAILABLE = False
    logger.warning("Alternative data not available")

try:
    from run_winning_strategy import scan as winning_scan, is_bull_regime
    WINNING_STRATEGY_AVAILABLE = True
except ImportError:
    WINNING_STRATEGY_AVAILABLE = False
    logger.warning("Winning strategy (backtested) not available")

# Load config
DEFAULT_CONFIG = {
    'TELEGRAM_BOT_TOKEN': '',
    'TELEGRAM_CHAT_ID': '',
    'TELEGRAM_ENABLED': True,
    'WATCHLIST': ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL'],
}

def normalize_config(raw_config):
    """Bridge old and new config keys into one runtime contract."""
    config = dict(DEFAULT_CONFIG)
    config.update(raw_config or {})

    if 'SENTIMENT_ENABLED' not in config:
        config['SENTIMENT_ENABLED'] = bool(
            config.get('USE_ADVANCED_SENTIMENT', True)
            or config.get('ENABLE_REDDIT_SENTIMENT', False)
        )

    if 'MOMENTUM_ENABLED' not in config:
        config['MOMENTUM_ENABLED'] = True

    if 'INSIDER_ENABLED' not in config:
        config['INSIDER_ENABLED'] = True

    if 'ALTERNATIVE_DATA_ENABLED' not in config:
        config['ALTERNATIVE_DATA_ENABLED'] = True

    return config

def load_config():
    """Load configuration"""
    try:
        with open('trading_config.json', 'r') as f:
            return normalize_config(json.load(f))
    except Exception as e:
        logger.error(f"Config error: {e}")
        return normalize_config({})

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

def get_simple_signal_from_df(df, ticker: str = ""):
    """Compute technical signal from a DataFrame (for backtesting on historical slices).
    df must have Close, at least 50 rows for SMA50."""
    try:
        if df is None or len(df) < 50:
            return None
        df = df.copy()
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        current_price = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2])
        change_pct = ((current_price - prev_close) / prev_close) * 100
        sma_20 = float(df["Close"].rolling(window=20).mean().iloc[-1])
        sma_50 = float(df["Close"].rolling(window=50).mean().iloc[-1])
        rsi = calculate_rsi(df)
        macd, signal_line = calculate_macd(df)
        signal_score = 0
        reasons = []
        if current_price > sma_20 and current_price > sma_50:
            signal_score += 1
            reasons.append("Price above MAs")
        elif current_price < sma_20 and current_price < sma_50:
            signal_score -= 1
            reasons.append("Price below MAs")
        if sma_20 > sma_50:
            signal_score += 1
            reasons.append("Golden cross (20>50)")
        else:
            signal_score -= 1
            reasons.append("Death cross (20<50)")
        if rsi < 30:
            signal_score += 2
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            signal_score -= 2
            reasons.append(f"RSI overbought ({rsi:.1f})")
        if macd > signal_line:
            signal_score += 1
            reasons.append("MACD bullish")
        else:
            signal_score -= 1
            reasons.append("MACD bearish")
        if signal_score >= 2:
            signal_type = "🟢 BUY"
        elif signal_score <= -2:
            signal_type = "🔴 SELL"
        else:
            signal_type = "⚪ HOLD"
        return {
            "ticker": ticker,
            "price": current_price,
            "change_pct": change_pct,
            "signal": signal_type,
            "signal_score": signal_score,
            "rsi": rsi,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "macd": macd,
            "macd_signal": signal_line,
            "reasons": reasons,
        }
    except Exception as e:
        logger.error(f"Signal from df failed: {e}")
        return None


def get_simple_signal(ticker: str):
    """Get a simple trading signal (fetches data from Yahoo Finance)."""
    try:
        df = get_stock_data(ticker, days=90)
        if df is None or len(df) < 50:
            return None
        return get_simple_signal_from_df(df, ticker)
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
    
    # Add trades tracking if available
    if TRADE_TRACKER_AVAILABLE:
        keyboard.append([InlineKeyboardButton("📊 Trade Performance", callback_data='trades')])
    if INSIDER_AVAILABLE:
        keyboard.append([InlineKeyboardButton("📄 Insider/Filings", callback_data='insider')])
    if ALTERNATIVE_DATA_AVAILABLE:
        keyboard.append([InlineKeyboardButton("📈 Alternative Data", callback_data='altdata')])
    if WINNING_STRATEGY_AVAILABLE:
        keyboard.append([InlineKeyboardButton("📈 Backtested Signals", callback_data='signals')])
    
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
    
    if TRADE_TRACKER_AVAILABLE:
        welcome_text += "\n• /trades - View trade performance"
    if INSIDER_AVAILABLE:
        welcome_text += "\n• /insider TICKER - SEC filings & insider activity"
    if ALTERNATIVE_DATA_AVAILABLE:
        welcome_text += "\n• /altdata TICKER - Trends & GitHub (alternative data)"
    if WINNING_STRATEGY_AVAILABLE:
        welcome_text += "\n• /signals - Backtested signals (earnings beat, hold 40d)"
    
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
    
    # Get sentiment data if available
    sentiment_data = None
    if SENTIMENT_AVAILABLE:
        try:
            sentiment_data = get_sentiment_signal(ticker, config)
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
    
    # Get momentum data if available
    momentum_data = None
    if MOMENTUM_AVAILABLE:
        try:
            momentum_data = get_momentum_signal(ticker, config)
        except Exception as e:
            logger.warning(f"Momentum analysis failed: {e}")

    # Get insider/filings data if available
    insider_data = None
    if INSIDER_AVAILABLE:
        try:
            insider_data = get_insider_signal(ticker, config)
        except Exception as e:
            logger.warning(f"Insider analysis failed: {e}")

    # Get alternative data if available (Trends, GitHub)
    alt_data = None
    if ALTERNATIVE_DATA_AVAILABLE:
        try:
            alt_data = get_alternative_data_signal(ticker, config)
        except Exception as e:
            logger.warning(f"Alternative data failed: {e}")
    
    # Format the response
    response = f"""
📊 **{result['ticker']} Analysis**

💰 Price: ${result['price']:.2f} ({result['change_pct']:+.2f}%)
"""
    
    # Add momentum signals if available (Market Cipher style)
    if momentum_data:
        response += f"\n**🌊 Momentum Intelligence:**\n"
        if momentum_data.green_diamond:
            response += f"💎 **GREEN DIAMOND** - Bullish Reversal ({momentum_data.diamond_confidence:.0%})\n"
        elif momentum_data.red_diamond:
            response += f"💎 **RED DIAMOND** - Bearish Reversal ({momentum_data.diamond_confidence:.0%})\n"
        if momentum_data.blood_diamond:
            response += f"💎 **BLOOD DIAMOND** - Strong Bearish (OpenCipher)\n"
        
        response += f"• Overall: **{momentum_data.overall_signal}** ({momentum_data.signal_confidence:.0%})\n"
        response += f"• Momentum: {momentum_data.momentum_trend} ({momentum_data.momentum_wave:.1f})\n"
        response += f"• Money Flow: {momentum_data.money_flow_index:.0f}/100\n"
        response += f"• Institutional: {momentum_data.institutional_pressure}\n"
        response += f"• Zone: {momentum_data.pressure_zone}\n"
        
        if momentum_data.momentum_divergence:
            response += f"⚠️ **DIVERGENCE DETECTED**\n"
    
    response += f"""
**Technical Indicators:**
• RSI: {result['rsi']:.1f}
• SMA 20: ${result['sma_20']:.2f}
• SMA 50: ${result['sma_50']:.2f}
• MACD: {result['macd']:.2f}

**Technical Signal:** {result['signal']} (Score: {result['signal_score']})
"""
    
    # Add sentiment if available
    if sentiment_data:
        sentiment_emoji = "🟢" if sentiment_data.sentiment_score > 0.2 else "🔴" if sentiment_data.sentiment_score < -0.2 else "⚪"
        response += f"""
**Social Sentiment:** {sentiment_emoji}
• Score: {sentiment_data.sentiment_score:+.1%}
• Mentions: {sentiment_data.mention_count} (24h)
• Velocity: {sentiment_data.velocity_score:.0%}
"""
        if sentiment_data.trending_rank:
            response += f"• Trending: #{sentiment_data.trending_rank}\n"

    # Add insider/filings if available
    if insider_data and insider_data.data_quality > 0:
        ins_emoji = "🟢" if insider_data.edge_signal >= 0.6 else "🔴" if insider_data.edge_signal <= 0.4 else "⚪"
        response += f"""
**Insider/Filings:** {ins_emoji}
• Edge score: {insider_data.edge_signal:.0%} (confidence: {insider_data.confidence:.0%})
• {insider_data.filing_summary}
"""

    # Add alternative data if available (Trends, GitHub)
    if alt_data and alt_data.data_quality > 0:
        alt_emoji = "🟢" if alt_data.edge_signal >= 0.6 else "🔴" if alt_data.edge_signal <= 0.4 else "⚪"
        response += f"""
**Alternative Data:** {alt_emoji}
• Edge: {alt_data.edge_signal:.0%} (confidence: {alt_data.confidence:.0%})
"""
        if alt_data.trend_score is not None:
            response += f"• Google Trends: {alt_data.trend_score:.0f}/100 ({alt_data.trend_direction})\n"
        if alt_data.github_stars > 0:
            response += f"• GitHub: {alt_data.github_stars} stars ({alt_data.github_repos} repos)\n"
    
    # Add reasoning section
    response += "\n**📋 Analysis:**\n"
    
    if momentum_data and momentum_data.key_factors:
        response += f"**Momentum Factors:** {', '.join(momentum_data.key_factors[:3])}\n"
    
    response += "**Technical:** "
    response += ", ".join(result['reasons'][:3]) + "\n"
    
    if sentiment_data:
        response += f"**Social:** {sentiment_data.reasoning[:100]}...\n"
    if insider_data and insider_data.data_quality > 0:
        response += f"**Filings:** {insider_data.reasoning[:80]}...\n"
    if alt_data and alt_data.data_quality > 0:
        response += f"**Alt data:** {alt_data.reasoning[:80]}...\n"

    # Auto-log strong signals to trade tracker
    if TRADE_TRACKER_AVAILABLE:
        should_log = False
        signal_type = "HOLD"
        confidence = 0.5
        edge_sources = []
        
        # Determine if we should log this trade
        if momentum_data:
            if momentum_data.green_diamond:
                should_log = True
                signal_type = "STRONG_BUY"
                confidence = momentum_data.diamond_confidence
                edge_sources.append("Momentum (Green Diamond)")
            elif momentum_data.red_diamond:
                should_log = True
                signal_type = "STRONG_SELL"
                confidence = momentum_data.diamond_confidence
                edge_sources.append("Momentum (Red Diamond)")
            if momentum_data.blood_diamond:
                should_log = True
                signal_type = "STRONG_SELL"
                confidence = momentum_data.diamond_confidence
                edge_sources.append("Momentum (Blood Diamond)")
            elif momentum_data.overall_signal in ["STRONG_BUY", "STRONG_SELL"]:
                should_log = True
                signal_type = momentum_data.overall_signal
                confidence = momentum_data.signal_confidence
                edge_sources.append(f"Momentum ({momentum_data.momentum_trend})")
        
        # Add other edge sources if they agree
        if sentiment_data and sentiment_data.velocity_score > 0.8:
            edge_sources.append("Sentiment (High Velocity)")
        
        if result['signal'] in ["🟢 BUY", "🔴 SELL"] and result['signal_score'] >= 3:
            edge_sources.append("Technical (Strong)")

        if insider_data and insider_data.data_quality > 0 and insider_data.confidence >= 0.5:
            if insider_data.edge_signal >= 0.65:
                edge_sources.append("Insider (bullish filings)")
            elif insider_data.edge_signal <= 0.35:
                edge_sources.append("Insider (bearish filings)")

        if alt_data and alt_data.data_quality > 0 and alt_data.confidence >= 0.5:
            if alt_data.edge_signal >= 0.65:
                edge_sources.append("Alternative data (strong interest)")
            elif alt_data.edge_signal <= 0.35:
                edge_sources.append("Alternative data (weak interest)")
        
        # Log if strong signal
        if should_log and confidence >= 0.65:
            comment_parts = []
            if momentum_data:
                comment_parts.append(f"Momentum: {momentum_data.momentum_trend}")
            if sentiment_data:
                comment_parts.append(f"Sentiment: {sentiment_data.sentiment_score:+.1%}")
            if insider_data and insider_data.data_quality > 0:
                comment_parts.append(f"Insider: {insider_data.edge_signal:.0%}")
            if alt_data and alt_data.data_quality > 0:
                comment_parts.append(f"Alt: {alt_data.edge_signal:.0%}")
            comment_parts.append(f"Technical: {result['signal']}")
            
            comment = ", ".join(comment_parts)
            
            trade_id = log_approved_trade(
                ticker=ticker,
                entry_price=result['price'],
                signal_type=signal_type,
                confidence=confidence,
                edge_sources=edge_sources if edge_sources else ["Technical"],
                comment=comment
            )
            
            if trade_id:
                response += f"\n\n✅ **Trade logged:** {trade_id}\n"
                response += f"📊 View all trades: /trades"
    
    response += f"\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Remove Markdown parsing to avoid special character issues
    await update.message.reply_text(response)

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
    
    await update.message.reply_text(response)

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command"""
    # Handle both direct commands and button callbacks
    message = update.callback_query.message if update.callback_query else update.message
    await message.reply_text("🔍 Scanning watchlist...")
    
    watchlist = config.get('WATCHLIST', ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL'])
    signals = []
    
    for ticker in watchlist[:10]:  # Limit to 10
        result = get_simple_signal(ticker)
        if result and result['signal'] != "⚪ HOLD":
            signals.append(result)
    
    if not signals:
        await message.reply_text("✅ No strong signals found. Market looks neutral.")
        return
    
    response = f"📊 Scan Results ({len(signals)} signals)\n\n"
    
    for result in signals:
        response += f"{result['signal']} {result['ticker']} ${result['price']:.2f}\n"
        response += f"  Score: {result['signal_score']}, RSI: {result['rsi']:.1f}\n\n"
    
    await message.reply_text(response)

async def david_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /david command - Small-cap opportunities"""
    # Handle both direct commands and button callbacks
    message = update.callback_query.message if update.callback_query else update.message
    
    if not DAVID_AVAILABLE:
        await message.reply_text("❌ David strategy not available. Install required packages.")
        return
    
    await message.reply_text("🎯 Scanning for small-cap opportunities...\n⏱️ This may take 30-60 seconds...")
    
    try:
        # Run the David strategy scan
        report = await scan_david_opportunities()
        
        # Split report if too long (Telegram limit is 4096 chars)
        if len(report) > 4000:
            parts = [report[i:i+3900] for i in range(0, len(report), 3900)]
            for i, part in enumerate(parts, 1):
                await message.reply_text(f"📊 Part {i}/{len(parts)}:\n\n{part}")
        else:
            await message.reply_text(report)
            
    except Exception as e:
        logger.error(f"David strategy error: {e}")
        await message.reply_text(f"❌ Error running David strategy: {str(e)}")

async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trades command - Show trade performance"""
    # Handle both direct commands and button callbacks
    message = update.callback_query.message if update.callback_query else update.message
    
    if not TRADE_TRACKER_AVAILABLE:
        await message.reply_text("❌ Trade tracker not available")
        return
    
    await message.reply_text("📊 Generating trade performance report...")
    
    try:
        report = get_performance_report()
        await message.reply_text(report)
    except Exception as e:
        logger.error(f"Trades command error: {e}")
        await message.reply_text(f"❌ Error generating report: {str(e)}")

async def insider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /insider command - SEC filings and insider activity for a ticker"""
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message

    if not INSIDER_AVAILABLE:
        await message.reply_text("❌ Insider intelligence not available")
        return

    if not context.args:
        await message.reply_text("Usage: /insider TICKER\nExample: /insider AAPL")
        return

    ticker = context.args[0].upper()
    await message.reply_text(f"📄 Fetching SEC filings for {ticker}...")

    try:
        signal = get_insider_signal(ticker, config)
        if not signal or signal.data_quality == 0:
            await message.reply_text(f"❌ No filing data for {ticker}. (Not in EDGAR or no recent filings.)")
            return

        emoji = "🟢" if signal.edge_signal >= 0.6 else "🔴" if signal.edge_signal <= 0.4 else "⚪"
        reply = f"""
📄 **Insider/Filings: {ticker}** {emoji}

• Edge score: {signal.edge_signal:.0%} (confidence: {signal.confidence:.0%})
• {signal.filing_summary}

**Summary:** {signal.reasoning}

Data quality: {signal.data_quality:.0%}
"""
        await message.reply_text(reply)
    except Exception as e:
        logger.error(f"Insider command error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def altdata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /altdata command - Google Trends & GitHub for a ticker"""
    if update.callback_query:
        message = update.callback_query.message
        await update.callback_query.answer()
    else:
        message = update.message

    if not ALTERNATIVE_DATA_AVAILABLE:
        await message.reply_text("❌ Alternative data not available")
        return

    if not context.args:
        await message.reply_text("Usage: /altdata TICKER\nExample: /altdata AAPL")
        return

    ticker = context.args[0].upper()
    await message.reply_text(f"📈 Fetching alternative data for {ticker}...")

    try:
        signal = get_alternative_data_signal(ticker, config)
        if not signal or signal.data_quality == 0:
            await message.reply_text(f"❌ No alternative data for {ticker}. (Install pytrends for Trends: pip install pytrends)")
            return

        emoji = "🟢" if signal.edge_signal >= 0.6 else "🔴" if signal.edge_signal <= 0.4 else "⚪"
        reply = f"""
📈 **Alternative Data: {ticker}** {emoji}

• Edge: {signal.edge_signal:.0%} (confidence: {signal.confidence:.0%})
"""
        if signal.trend_score is not None:
            reply += f"• Google Trends: {signal.trend_score:.0f}/100 ({signal.trend_direction})\n"
        if signal.github_stars > 0:
            reply += f"• GitHub: {signal.github_stars} stars, {signal.github_repos} repos\n"
        reply += f"• {signal.web_traffic_note}\n"
        reply += f"• {signal.app_rank_note}\n\n**Summary:** {signal.reasoning}"
        await message.reply_text(reply)
    except Exception as e:
        logger.error(f"Altdata command error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /signals — backtested winning strategy (earnings beat 40-100%, hold 40d, bull only)."""
    message = update.callback_query.message if update.callback_query else update.message
    if not WINNING_STRATEGY_AVAILABLE:
        await message.reply_text("❌ Winning strategy module not available.")
        return
    await message.reply_text("📊 Scanning for backtested signals (earnings beat 40-100%, bull regime) ...")
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, winning_scan, None)
        bull = is_bull_regime()
        if not bull:
            await message.reply_text(
                "⚠️ **Not in bull regime** (SPY below 200d MA).\n"
                "No new entries per strategy rules. Wait for SPY > 200d MA.",
                parse_mode="Markdown"
            )
            return
        if not results:
            await message.reply_text(
                "✅ Bull regime. No current signals in the last 15 days "
                "(no earnings beat in 40-100% surprise range)."
            )
            return
        lines = [f"• **{r['ticker']}**  earnings {r['earnings_date']}  surprise **{r['surprise_pct']:+.1f}%**  ${r['price']}  (hold 40d)" for r in results]
        reply = "📈 **Backtested signals** (hold 40 days)\n\n" + "\n".join(lines)
        await message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Signals command error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    # Handle both direct commands and button callbacks
    message = update.callback_query.message if update.callback_query else update.message
    
    help_text = """
ℹ️ Simple Trading Bot Help

Commands:
• /start - Show main menu
• /analyze TICKER - Analyze any stock
• /watchlist - View your watchlist
• /scan - Scan watchlist for signals"""
    
    if DAVID_AVAILABLE:
        help_text += "\n• /david - Find small-cap opportunities (David vs Goliath)"
    
    if TRADE_TRACKER_AVAILABLE:
        help_text += "\n• /trades - View trade performance & win rate"
    if INSIDER_AVAILABLE:
        help_text += "\n• /insider TICKER - SEC filings & insider activity"
    if ALTERNATIVE_DATA_AVAILABLE:
        help_text += "\n• /altdata TICKER - Google Trends & GitHub (alternative data)"
    if WINNING_STRATEGY_AVAILABLE:
        help_text += "\n• /signals - Backtested strategy: earnings beat 40-100%, hold 40d (bull only)"
    
    help_text += """
• /help - Show this help

How it works:
The bot uses multiple edge sources:
• Technical Analysis (RSI, MACD, MAs)
• Momentum Intelligence (Market Cipher-style diamonds 💎)
• Sentiment Intelligence (Reddit trending)
• David Strategy (Small-cap opportunities)
• Insider Intelligence (SEC filings, Form 4)
• Alternative Data (Google Trends, GitHub)

Signals:
🟢 BUY - Bullish indicators
🔴 SELL - Bearish indicators
💎 GREEN DIAMOND - Strong bullish reversal
💎 RED DIAMOND - Strong bearish reversal

Trade Tracking:
Strong signals are automatically logged.
Use /trades to see performance!

Example:
/analyze AAPL

Revolutionary and reliable! 📈🚀
"""
    
    await message.reply_text(help_text)

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
    elif query.data == 'trades':
        if TRADE_TRACKER_AVAILABLE:
            await query.message.reply_text("📊 Loading trade performance...")
            await trades_command(update, context)
        else:
            await query.message.reply_text("❌ Trade tracker not available")
    elif query.data == 'insider':
        if INSIDER_AVAILABLE:
            await query.message.reply_text("Type: /insider TICKER\nExample: /insider AAPL")
        else:
            await query.message.reply_text("❌ Insider intelligence not available")
    elif query.data == 'altdata':
        if ALTERNATIVE_DATA_AVAILABLE:
            await query.message.reply_text("Type: /altdata TICKER\nExample: /altdata AAPL")
        else:
            await query.message.reply_text("❌ Alternative data not available")
    elif query.data == 'signals':
        if WINNING_STRATEGY_AVAILABLE:
            await query.message.reply_text("📊 Loading backtested signals...")
            await signals_command(update, context)
        else:
            await query.message.reply_text("❌ Winning strategy not available")
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
    if not config.get('TELEGRAM_ENABLED', True):
        print("ℹ️ Telegram is disabled in trading_config.json")
        return

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
        
        # Print sentiment status
        if SENTIMENT_AVAILABLE:
            print("✅ Sentiment Intelligence loaded")
        
        # Print momentum status
        if MOMENTUM_AVAILABLE:
            print("✅ Momentum Intelligence loaded (Market Cipher-style)")
        
        # Add trades command if available
        if TRADE_TRACKER_AVAILABLE:
            application.add_handler(CommandHandler("trades", trades_command))
            print("✅ Trade Tracker loaded (Auto-logs strong signals)")
        if INSIDER_AVAILABLE:
            application.add_handler(CommandHandler("insider", insider_command))
            print("✅ Insider Intelligence loaded (SEC EDGAR filings)")
        if ALTERNATIVE_DATA_AVAILABLE:
            application.add_handler(CommandHandler("altdata", altdata_command))
            print("✅ Alternative Data loaded (Trends, GitHub)")
        if WINNING_STRATEGY_AVAILABLE:
            application.add_handler(CommandHandler("signals", signals_command))
            print("✅ Backtested winning strategy loaded (/signals)")
        
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        print("✅ Handlers registered")
        
        # Show edge sources
        edge_count = 1  # Technical always available
        if DAVID_AVAILABLE:
            edge_count += 1
        if SENTIMENT_AVAILABLE:
            edge_count += 1
        if MOMENTUM_AVAILABLE:
            edge_count += 1
        if INSIDER_AVAILABLE:
            edge_count += 1
        if ALTERNATIVE_DATA_AVAILABLE:
            edge_count += 1
        if WINNING_STRATEGY_AVAILABLE:
            edge_count += 1
        
        print(f"\n🚀 Bot is running with {edge_count} edge sources!")
        print("📊 Edge Sources:")
        print("   • Technical Analysis (RSI, MACD, MAs)")
        if DAVID_AVAILABLE:
            print("   • David vs Goliath (Small-cap opportunities)")
        if SENTIMENT_AVAILABLE:
            print("   • Sentiment Intelligence (Reddit, social media)")
        if MOMENTUM_AVAILABLE:
            print("   • Momentum Intelligence (Diamonds, waves, pressure)")
        if INSIDER_AVAILABLE:
            print("   • Insider Intelligence (SEC filings, Form 4)")
        if ALTERNATIVE_DATA_AVAILABLE:
            print("   • Alternative Data (Google Trends, GitHub)")
        if WINNING_STRATEGY_AVAILABLE:
            print("   • Backtested strategy (earnings beat 40-100%, hold 40d)")
        
        if TRADE_TRACKER_AVAILABLE:
            print("\n📊 Trade Tracking:")
            print("   • Auto-logs strong signals (💎 diamonds, STRONG_BUY/SELL)")
            print("   • Tracks performance over time")
            print("   • View with /trades command")
        
        print("\n📱 Open Telegram and send /start to your bot")
        print("⏹️  Press Ctrl+C to stop\n")
        
        # Start polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Bot error: {e}")

if __name__ == "__main__":
    main()

