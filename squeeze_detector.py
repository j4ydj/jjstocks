#!/usr/bin/env python3
"""
SHORT SQUEEZE DETECTOR
======================
EDGE: High short interest + volume surge + price uptick = forced covering.
DATA: yfinance .info (short interest) + price/volume history (free).
WHY:  Squeezes are mechanical — shorts MUST buy to cover, creating predictable
      explosive moves.  We detect the setup before the cascade.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "ENABLED": True,
    "MIN_SHORT_FLOAT_PCT": 10.0,  # minimum % of float shorted
    "MIN_DAYS_TO_COVER": 3.0,
    "MIN_VOLUME_MULTIPLE": 1.5,   # current vol vs 20d avg
    "MIN_PRICE_CHANGE_PCT": 2.0,  # minimum recent price move up
}


@dataclass
class SqueezeSignal:
    ticker: str
    signal: str             # "SQUEEZE_SETUP", "WATCH", "NONE"
    short_pct_float: Optional[float]
    days_to_cover: Optional[float]
    volume_multiple: float  # today vol / 20d avg
    price_change_5d: float  # 5-day % change
    score: float            # 0-100
    confidence: float       # 0-1
    reasons: List[str] = field(default_factory=list)


def analyze_squeeze(ticker: str, config: dict = None) -> Optional[SqueezeSignal]:
    """Detect short squeeze setup for a single ticker."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if not cfg.get("ENABLED", True):
        return None

    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        hist = tk.history(period="30d", interval="1d")
        if hist is None or len(hist) < 10:
            return None
    except Exception as e:
        logger.debug("squeeze data failed for %s: %s", ticker, e)
        return None

    short_pct = _float(info.get("shortPercentOfFloat"))
    if short_pct is not None:
        short_pct *= 100  # convert decimal to %

    short_ratio = _float(info.get("shortRatio"))  # days to cover

    close = hist["Close"]
    volume = hist["Volume"]

    if len(volume) < 5 or volume.iloc[-5:].sum() == 0:
        return None

    avg_vol_20 = float(volume.rolling(20, min_periods=5).mean().iloc[-1])
    latest_vol = float(volume.iloc[-1])
    vol_mult = latest_vol / avg_vol_20 if avg_vol_20 > 0 else 0

    price_now = float(close.iloc[-1])
    price_5d_ago = float(close.iloc[-5]) if len(close) >= 5 else float(close.iloc[0])
    price_chg_5d = ((price_now - price_5d_ago) / price_5d_ago) * 100 if price_5d_ago > 0 else 0

    # --- Scoring ---
    score = 0.0
    reasons = []

    # Short interest component
    if short_pct is not None and short_pct >= cfg["MIN_SHORT_FLOAT_PCT"]:
        score += min(35, short_pct * 1.5)
        reasons.append(f"Short float {short_pct:.1f}%")
    elif short_pct is not None:
        reasons.append(f"Low short float {short_pct:.1f}%")

    if short_ratio is not None and short_ratio >= cfg["MIN_DAYS_TO_COVER"]:
        score += min(20, short_ratio * 3)
        reasons.append(f"Days to cover: {short_ratio:.1f}")

    # Volume surge component
    if vol_mult >= cfg["MIN_VOLUME_MULTIPLE"]:
        score += min(25, vol_mult * 8)
        reasons.append(f"Volume surge {vol_mult:.1f}x avg")

    # Price action component
    if price_chg_5d >= cfg["MIN_PRICE_CHANGE_PCT"]:
        score += min(20, price_chg_5d * 2)
        reasons.append(f"Price +{price_chg_5d:.1f}% (5d)")
    elif price_chg_5d < 0:
        score -= 5

    score = max(0, min(100, score))

    if score >= 50:
        signal = "SQUEEZE_SETUP"
    elif score >= 25:
        signal = "WATCH"
    else:
        signal = "NONE"

    confidence = score / 100 * 0.8
    if short_pct is None:
        confidence *= 0.5  # lower confidence without SI data

    return SqueezeSignal(
        ticker=ticker,
        signal=signal,
        short_pct_float=round(short_pct, 1) if short_pct else None,
        days_to_cover=round(short_ratio, 1) if short_ratio else None,
        volume_multiple=round(vol_mult, 2),
        price_change_5d=round(price_chg_5d, 2),
        score=round(score, 1),
        confidence=round(confidence, 3),
        reasons=reasons,
    )


def scan_squeeze_universe(tickers: List[str], config: dict = None) -> List[SqueezeSignal]:
    """Scan for squeeze setups, return SQUEEZE_SETUP and WATCH sorted by score."""
    results = []
    for tk in tickers:
        sig = analyze_squeeze(tk, config)
        if sig and sig.signal in ("SQUEEZE_SETUP", "WATCH"):
            results.append(sig)
    results.sort(key=lambda s: s.score, reverse=True)
    return results


def _float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if not np.isnan(f) else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sample = ["SOFI", "PLUG", "FUBO", "HOOD", "RIVN", "LCID", "CRWD", "RKLB"]
    for s in scan_squeeze_universe(sample):
        si = f"SI={s.short_pct_float:.1f}%" if s.short_pct_float else "SI=N/A"
        print(f"  {s.ticker:6s}  {s.signal:14s}  score={s.score:5.1f}  {si}  "
              f"vol={s.volume_multiple:.1f}x  5d={s.price_change_5d:+.1f}%  "
              f"| {'; '.join(s.reasons[:2])}")
