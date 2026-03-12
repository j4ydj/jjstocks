#!/usr/bin/env python3
"""
VOLUME ANOMALY / ACCUMULATION DETECTOR
=======================================
EDGE: Unusual buying pressure precedes information events (M&A, earnings, FDA).
DATA: yfinance price/volume history (free).
WHY:  Large buyers can't hide their volume footprint.  Spikes and OBV breakouts
      detect institutional accumulation before the news drops.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "ENABLED": True,
    "SPIKE_THRESHOLD": 2.5,        # current vol / 20d avg
    "ACCUMULATION_DAYS": 10,       # window to detect quiet accumulation
    "OBV_LOOKBACK": 60,            # bars for OBV breakout check
    "PRICE_VOLUME_CONFIRM": True,  # require price+volume to agree
}


@dataclass
class VolumeSignal:
    ticker: str
    signal: str               # "ACCUMULATION", "SPIKE_BUY", "DISTRIBUTION", "NONE"
    volume_multiple: float    # latest vol / 20d avg
    obv_breakout: bool        # OBV at 20-day high while price isn't
    accumulation_score: float # 0-100 based on price-volume relationship
    price_change_5d: float
    confidence: float         # 0-1
    reasons: List[str] = field(default_factory=list)


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def _accumulation_distribution(close: pd.Series, volume: pd.Series,
                                high: pd.Series, low: pd.Series) -> float:
    """Accumulation/Distribution ratio over last N bars."""
    hl = high - low
    hl = hl.replace(0, np.nan)
    clv = ((close - low) - (high - close)) / hl
    ad = (clv * volume).fillna(0)
    recent = ad.iloc[-10:]
    if recent.sum() == 0:
        return 0.0
    return float(recent.sum() / abs(recent).sum())  # -1 to +1


def analyze_volume(ticker: str, config: dict = None) -> Optional[VolumeSignal]:
    """Detect volume anomalies for a single ticker."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if not cfg.get("ENABLED", True):
        return None

    try:
        df = yf.Ticker(ticker).history(period="90d", interval="1d")
        if df is None or len(df) < 30:
            return None
    except Exception as e:
        logger.debug("volume data failed for %s: %s", ticker, e)
        return None

    close = df["Close"]
    volume = df["Volume"]
    high = df["High"]
    low = df["Low"]

    avg_vol_20 = float(volume.rolling(20, min_periods=10).mean().iloc[-1])
    latest_vol = float(volume.iloc[-1])
    vol_mult = latest_vol / avg_vol_20 if avg_vol_20 > 0 else 0

    # Price changes
    price_now = float(close.iloc[-1])
    price_5d = float(close.iloc[-5]) if len(close) >= 5 else float(close.iloc[0])
    price_chg_5d = ((price_now - price_5d) / price_5d) * 100 if price_5d > 0 else 0

    # OBV analysis
    obv = _obv(close, volume)
    obv_now = float(obv.iloc[-1])
    obv_20d_high = float(obv.iloc[-20:].max()) if len(obv) >= 20 else obv_now
    price_20d_high = float(close.iloc[-20:].max()) if len(close) >= 20 else price_now
    obv_breakout = (obv_now >= obv_20d_high * 0.98) and (price_now < price_20d_high * 0.97)

    # A/D ratio
    ad_ratio = _accumulation_distribution(close, volume, high, low)

    # --- Scoring ---
    score = 50.0  # neutral baseline
    reasons = []

    # Volume spike
    spike_thresh = cfg["SPIKE_THRESHOLD"]
    if vol_mult >= spike_thresh:
        score += min(25, (vol_mult - spike_thresh) * 10 + 15)
        reasons.append(f"Volume spike {vol_mult:.1f}x avg")
    elif vol_mult >= 1.5:
        score += 5
        reasons.append(f"Elevated volume {vol_mult:.1f}x")

    # OBV divergence (bullish: OBV breaking out while price hasn't)
    if obv_breakout:
        score += 15
        reasons.append("OBV breakout (bullish divergence)")

    # Accumulation/Distribution
    if ad_ratio > 0.3:
        score += 10
        reasons.append(f"Accumulation pattern (A/D={ad_ratio:+.2f})")
    elif ad_ratio < -0.3:
        score -= 10
        reasons.append(f"Distribution pattern (A/D={ad_ratio:+.2f})")

    # Price confirms
    if price_chg_5d > 0 and vol_mult > 1.2:
        score += 5
        reasons.append(f"Price +{price_chg_5d:.1f}% on volume")
    elif price_chg_5d < -3 and vol_mult > spike_thresh:
        score -= 15
        reasons.append(f"Sell-off on heavy volume")

    # Quiet accumulation: 5+ consecutive days with above-avg volume and small positive moves
    recent_vol = volume.iloc[-10:]
    recent_close = close.iloc[-10:]
    if len(recent_vol) >= 10:
        above_avg_days = (recent_vol > avg_vol_20).sum()
        positive_days = (recent_close.diff() > 0).sum()
        if above_avg_days >= 6 and positive_days >= 6:
            score += 10
            reasons.append(f"Quiet accumulation ({above_avg_days}/10 days above-avg vol)")

    score = max(0, min(100, score))

    # Determine signal type
    if score >= 70 and price_chg_5d >= 0:
        signal = "ACCUMULATION"
    elif vol_mult >= spike_thresh and price_chg_5d > 2:
        signal = "SPIKE_BUY"
    elif score <= 30 or (ad_ratio < -0.3 and price_chg_5d < -2):
        signal = "DISTRIBUTION"
    else:
        signal = "NONE"

    confidence = (score / 100) * 0.7

    return VolumeSignal(
        ticker=ticker,
        signal=signal,
        volume_multiple=round(vol_mult, 2),
        obv_breakout=obv_breakout,
        accumulation_score=round(score, 1),
        price_change_5d=round(price_chg_5d, 2),
        confidence=round(confidence, 3),
        reasons=reasons,
    )


def scan_volume_universe(tickers: List[str], config: dict = None) -> List[VolumeSignal]:
    """Scan tickers for volume anomalies, return actionable signals."""
    results = []
    for tk in tickers:
        sig = analyze_volume(tk, config)
        if sig and sig.signal in ("ACCUMULATION", "SPIKE_BUY"):
            results.append(sig)
    results.sort(key=lambda s: s.accumulation_score, reverse=True)
    return results


# --- Backtesting helper ---

def score_volume_at(df: pd.DataFrame, idx: int, lookback: int = 20) -> Optional[dict]:
    """Score volume anomaly at a specific bar index (for historical backtesting).
    Returns dict with score and signal, or None."""
    if idx < lookback + 10 or idx >= len(df):
        return None

    sl = df.iloc[max(0, idx - 90) : idx + 1]
    close = sl["Close"]
    volume = sl["Volume"]
    high = sl["High"]
    low = sl["Low"]

    if len(close) < 25:
        return None

    avg_vol = float(volume.rolling(lookback, min_periods=10).mean().iloc[-1])
    if avg_vol <= 0:
        return None
    vol_mult = float(volume.iloc[-1]) / avg_vol

    obv = _obv(close, volume)
    obv_now = float(obv.iloc[-1])
    obv_high = float(obv.iloc[-lookback:].max())
    price_now = float(close.iloc[-1])
    price_high = float(close.iloc[-lookback:].max())
    obv_breakout = (obv_now >= obv_high * 0.98) and (price_now < price_high * 0.97)

    ad = _accumulation_distribution(close, volume, high, low)

    score = 50.0
    if vol_mult >= 2.5:
        score += min(25, (vol_mult - 2.5) * 10 + 15)
    if obv_breakout:
        score += 15
    if ad > 0.3:
        score += 10
    elif ad < -0.3:
        score -= 10

    price_5d = float(close.iloc[-5]) if len(close) >= 5 else price_now
    pchg = ((price_now - price_5d) / price_5d) * 100 if price_5d > 0 else 0
    if pchg > 0 and vol_mult > 1.2:
        score += 5

    score = max(0, min(100, score))
    sig = "ACCUMULATION" if score >= 70 else ("SPIKE_BUY" if vol_mult >= 2.5 and pchg > 2 else "NONE")
    return {"score": score, "signal": sig, "vol_mult": vol_mult, "price": price_now}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sample = ["AAPL", "NVDA", "SOFI", "CRWD", "RKLB", "SOUN", "CAVA", "HOOD"]
    for s in scan_volume_universe(sample):
        print(f"  {s.ticker:6s}  {s.signal:14s}  vol={s.volume_multiple:.1f}x  "
              f"score={s.accumulation_score:.0f}  5d={s.price_change_5d:+.1f}%  "
              f"obv_brk={'Y' if s.obv_breakout else 'N'}  "
              f"| {'; '.join(s.reasons[:3])}")
