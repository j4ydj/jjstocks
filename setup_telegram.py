#!/usr/bin/env python3
"""
TELEGRAM SETUP HELPER
====================
Interactive setup for Telegram bot alerts.

Usage:
  python setup_telegram.py
"""
import os
import sys

TELEGRAM_CONFIG_FILE = ".telegram_config"

def setup():
    """Interactive setup."""
    print("=" * 70)
    print("  TELEGRAM BOT SETUP")
    print("=" * 70)
    
    print("\n📱 Step 1: Create Telegram Bot")
    print("   1. Open Telegram and search for @BotFather")
    print("   2. Click 'Start' and send: /newbot")
    print("   3. Choose a name for your bot (e.g., 'My Trading Bot')")
    print("   4. Choose a username (must end in 'bot', e.g., 'mytrades_bot')")
    print("   5. Copy the token BotFather gives you")
    print("\n   It looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
    
    print("\n" + "=" * 70)
    token = input("\nPaste your bot token: ").strip()
    
    if not token or ":" not in token:
        print("\n❌ Invalid token format")
        return False
    
    print("\n" + "=" * 70)
    print("\n👤 Step 2: Get Your Chat ID")
    print("   1. Search for @userinfobot in Telegram")
    print("   2. Click 'Start'")
    print("   3. Copy the 'Id' number shown")
    print("\n   It looks like: 123456789")
    
    print("\n" + "=" * 70)
    chat_id = input("\nPaste your chat ID: ").strip()
    
    if not chat_id.isdigit():
        print("\n❌ Chat ID should be numbers only")
        return False
    
    # Save configuration
    config = {
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_ID": chat_id
    }
    
    # Save to file
    with open(TELEGRAM_CONFIG_FILE, 'w') as f:
        for key, value in config.items():
            f.write(f"export {key}={value}\n")
    
    print("\n" + "=" * 70)
    print("✅ Configuration saved!")
    print(f"📁 Saved to: {TELEGRAM_CONFIG_FILE}")
    print("\nTo activate, run:")
    print(f"   source {TELEGRAM_CONFIG_FILE}")
    print("\nOr add to your shell profile (.bashrc/.zshrc):")
    print(f"   echo 'source {os.path.abspath(TELEGRAM_CONFIG_FILE)}' >> ~/.zshrc")
    
    # Test immediately
    print("\n" + "=" * 70)
    test = input("\n🧪 Test the connection now? (y/n): ").strip().lower()
    
    if test == 'y':
        os.environ["TELEGRAM_BOT_TOKEN"] = token
        os.environ["TELEGRAM_CHAT_ID"] = chat_id
        
        try:
            from telegram_alerts import TelegramBot
            bot = TelegramBot()
            
            if bot.send_message("🎉 <b>Trading Bot Activated!</b>\n\nYour edge system is now connected.\nYou'll receive alerts when trading signals are found."):
                print("\n✅ Test message sent successfully!")
                print("📲 Check your Telegram for the message")
            else:
                print("\n❌ Failed to send test message")
                print("Check your token and chat ID")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("Setup complete!")
    print("\nTo run scans with Telegram alerts:")
    print("   source .telegram_config")
    print("   python telegram_alerts.py")
    print("\nOr for scheduled alerts:")
    print("   python auto_runner.py --schedule daily")
    print("=" * 70)
    
    return True

def test_existing():
    """Test existing configuration."""
    from telegram_alerts import TelegramBot
    
    bot = TelegramBot()
    
    if not bot.enabled:
        print("❌ Not configured. Run: python setup_telegram.py")
        return False
    
    print("🧪 Sending test message...")
    if bot.send_message("🧪 <b>Test</b>\nBot is working correctly!"):
        print("✅ Success! Check your Telegram")
        return True
    else:
        print("❌ Failed. Check your configuration")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Test existing config")
    args = parser.parse_args()
    
    if args.test:
        test_existing()
    else:
        setup()

if __name__ == "__main__":
    main()
