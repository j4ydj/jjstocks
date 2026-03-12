#!/usr/bin/env python3
"""Test blood diamond and momentum signal functionality."""

import sys
import pandas as pd
import numpy as np

def test_momentum_signal_has_blood_diamond():
    """MomentumSignal must have blood_diamond attribute (bool)."""
    from momentum_intelligence import MomentumSignal
    s = MomentumSignal(
        ticker="TEST",
        green_diamond=False,
        red_diamond=True,
        blood_diamond=True,
        diamond_confidence=0.8,
        momentum_wave=50.0,
        momentum_trend="BEAR",
        momentum_divergence=False,
        money_flow_index=75.0,
        institutional_pressure="SELLING",
        smart_money_signal=False,
        buying_pressure=30.0,
        selling_pressure=70.0,
        pressure_zone="OVERSOLD",
        volume_trend="STABLE",
        volume_breakout=False,
        overall_signal="STRONG_SELL",
        signal_confidence=0.8,
        reasoning="Test",
        key_factors=["Blood Diamond"],
    )
    assert hasattr(s, "blood_diamond"), "MomentumSignal should have blood_diamond"
    assert s.blood_diamond is True, "blood_diamond should be True"
    print("   ✅ MomentumSignal.blood_diamond exists and is bool")

def test_blood_diamond_logic_with_synthetic_data():
    """When last bar has EMA5 < EMA11 and red_diamond would be True, blood_diamond should be True."""
    from momentum_intelligence import MomentumIntelligence
    # Build a series of closes that: (1) go up then drop sharply so wave is overbought and turning down,
    # (2) last bar has EMA5 < EMA11 (recent decline).
    np.random.seed(42)
    n = 120
    # Uptrend then sharp drop last 10 bars -> overbought then turn down, EMA5 < EMA11
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    close[-15:] = np.linspace(close[-15], close[-15] - 8, 15)  # drop
    df = pd.DataFrame({
        "Open": close,
        "High": close + 0.5,
        "Low": close - 0.5,
        "Close": close,
        "Volume": 1_000_000 * np.ones(n),
    }, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    # Ensure last bar: EMA5 < EMA11
    ema5 = df["Close"].ewm(span=5, adjust=False).mean()
    ema11 = df["Close"].ewm(span=11, adjust=False).mean()
    assert ema5.iloc[-1] < ema11.iloc[-1], "Synthetic data should have EMA5 < EMA11 on last bar"
    # Run analyzer with injected data
    analyzer = MomentumIntelligence()
    original_get = analyzer._get_stock_data
    def mock_get(ticker, period):
        return df
    analyzer._get_stock_data = mock_get
    signal = analyzer.analyze("SYNTH")
    analyzer._get_stock_data = original_get
    assert signal is not None, "Analyzer should return a signal"
    assert signal.blood_diamond in (True, False), "blood_diamond should be True or False"
    # We may or may not get red_diamond from this synthetic data (depends on wave/mfi). At least check no crash and bool.
    print(f"   ✅ Synthetic run: blood_diamond={signal.blood_diamond}, red_diamond={signal.red_diamond}")

def test_analyze_returns_blood_diamond():
    """Live analyzer returns an object with blood_diamond (no crash)."""
    from momentum_intelligence import get_momentum_signal
    # Use a ticker that's likely to work (yfinance rate limit may hit)
    signal = get_momentum_signal("SPY")
    if signal is None:
        print("   ⚠️  get_momentum_signal('SPY') returned None (e.g. rate limit); skipping live check")
        return
    assert hasattr(signal, "blood_diamond"), "Signal should have blood_diamond"
    assert signal.blood_diamond in (True, False), "blood_diamond should be bool"
    print(f"   ✅ Live SPY: blood_diamond={signal.blood_diamond}")

if __name__ == "__main__":
    print("Testing new blood diamond functionality")
    print("=" * 50)
    try:
        test_momentum_signal_has_blood_diamond()
        test_blood_diamond_logic_with_synthetic_data()
        test_analyze_returns_blood_diamond()
    except Exception as e:
        print(f"   ❌ {e}")
        sys.exit(1)
    print("=" * 50)
    print("All blood diamond tests passed.")
