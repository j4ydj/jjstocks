#!/usr/bin/env python3
"""
Quick test of David vs Goliath strategy
"""
import asyncio
import sys

print("🎯 Testing David vs Goliath Strategy...")
print("=" * 60)

try:
    from david_portfolio_strategy import scan_david_opportunities
    print("✅ David strategy module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import David strategy: {e}")
    sys.exit(1)

async def quick_test():
    """Run a quick test scan"""
    print("\n🔍 Running small-cap opportunity scan...")
    print("⏱️  This will scan real stocks (may take 30-60 seconds)\n")
    
    try:
        # Run the scan
        report = await scan_david_opportunities()
        
        # Display results
        print("\n" + "=" * 60)
        print("📊 DAVID STRATEGY SCAN RESULTS:")
        print("=" * 60)
        print(report)
        print("\n✅ David strategy test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ David strategy error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(quick_test())

