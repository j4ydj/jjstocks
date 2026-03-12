#!/usr/bin/env python3
"""
Quick test of simple_trading_bot.py
Tests that basic functions work without running the Telegram bot
"""

import sys
import json
from pathlib import Path

print("🧪 Testing Simple Trading Bot...")
print("=" * 50)

venv_python = Path("venv/bin/python").resolve()
current_python = Path(sys.executable).resolve()

if venv_python.exists() and current_python != venv_python:
    print("⚠️  You are not using the repo virtualenv.")
    print(f"   Current: {current_python}")
    print(f"   Expected: {venv_python}")
    print("   💡 For the most reliable results use: ./venv/bin/python test_simple_bot.py")

# Test 1: Imports
print("\n1. Testing imports...")
try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    from telegram import Update
    from telegram.ext import Application
    print("   ✅ All imports successful")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    print("   💡 Run: pip install -r simple_requirements.txt")
    sys.exit(1)

# Test 2: Config loading
print("\n2. Testing config...")
try:
    with open('trading_config.json', 'r') as f:
        config = json.load(f)
    
    if config.get('TELEGRAM_BOT_TOKEN') and config['TELEGRAM_BOT_TOKEN'] != 'YOUR_BOT_TOKEN_HERE':
        print(f"   ✅ Config loaded")
        print(f"   📋 Watchlist: {', '.join(config.get('WATCHLIST', [])[:3])}...")
    else:
        print("   ⚠️  Config loaded but bot token not set")
        print("   💡 Set TELEGRAM_BOT_TOKEN in trading_config.json")
except FileNotFoundError:
    print("   ❌ trading_config.json not found")
    print("   💡 Copy simple_config.json to trading_config.json")
    sys.exit(1)

# Test 3: Stock data
print("\n3. Testing stock data...")
try:
    from simple_trading_bot import get_stock_data, get_simple_signal
    
    # Test with AAPL
    df = get_stock_data('AAPL', days=30)
    if df is not None and len(df) > 0:
        print(f"   ✅ Stock data retrieval works")
        print(f"   📊 AAPL data: {len(df)} days")
    else:
        print("   ⚠️  No data retrieved (might be after hours)")
except Exception as e:
    print(f"   ❌ Stock data error: {e}")

# Test 4: Signal generation
print("\n4. Testing signal generation...")
try:
    result = get_simple_signal('AAPL')
    if result:
        print(f"   ✅ Signal generation works")
        print(f"   💰 AAPL: ${result['price']:.2f}")
        print(f"   📊 Signal: {result['signal']}")
        print(f"   📈 RSI: {result['rsi']:.1f}")
    else:
        print("   ⚠️  Signal generation returned None")
except Exception as e:
    print(f"   ❌ Signal error: {e}")

# Test 5: Bot initialization (without running)
print("\n5. Testing bot initialization...")
if config.get('TELEGRAM_BOT_TOKEN') and config['TELEGRAM_BOT_TOKEN'] != 'YOUR_BOT_TOKEN_HERE':
    try:
        # Just test we can create the application object
        app = Application.builder().token(config['TELEGRAM_BOT_TOKEN']).build()
        print("   ✅ Bot can be initialized")
        print("   🤖 Ready to run!")
    except Exception as e:
        print(f"   ❌ Bot init error: {e}")
        if "proxy" in str(e).lower():
            print("   💡 This usually means the global Python packages are mismatched.")
            print("   💡 Use the repo virtualenv: ./venv/bin/python test_simple_bot.py")
        else:
            print("   💡 Check your bot token")
else:
    print("   ⚠️  Skipping (no bot token configured)")

# Summary
print("\n" + "=" * 50)
print("🎯 Test Summary:")
print("   If all tests passed, you're ready to run the bot!")
print("   Use: ./start_simple.sh")
print("   Or:  ./venv/bin/python simple_trading_bot.py")
print("=" * 50)

