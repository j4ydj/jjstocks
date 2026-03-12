#!/usr/bin/env python3
"""
EARNINGS SURPRISE DRIFT (PEAD)
==============================
EDGE: Stocks that beat earnings estimates drift up for 20-60 days after.
DATA: yfinance earnings calendar + quarterly financials (free).
WHY:  Post-Earnings Announcement Drift is one of the most robust anomalies
      in finance — the market systematically underreacts to earnings surprises.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "ENABLED": True,
    "MIN_SURPRISE_PCT": 10.0,   # |surprise| must exceed this to signal
    "LOOKBACK_DAYS": 10,        # how far back to look for recent earnings
    "HOLD_DAYS": 40,            # expected drift window
}


@dataclass
class EarningsDriftSignal:
    ticker: str
    signal: str            # "BUY" (beat) or "AVOID" (miss) or "NEUTRAL"
    surprise_pct: float    # positive = beat
    earnings_date: str
    eps_actual: Optional[float]
    eps_estimate: Optional[float]
    confidence: float      # 0-1, scales with surprise magnitude
    reasons: List[str] = field(default_factory=list)


def analyze_earnings(ticker: str, config: dict = None) -> Optional[EarningsDriftSignal]:
    """Check if ticker had a recent earnings surprise worth trading."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if not cfg.get("ENABLED", True):
        return None

    try:
        tk = yf.Ticker(ticker)
        ed = tk.earnings_dates
        if ed is None or ed.empty:
            return None
    except Exception as e:
        logger.debug("earnings_dates failed for %s: %s", ticker, e)
        return None

    now = pd.Timestamp.now()
    if hasattr(now, "tz_localize") and now.tzinfo is None and ed.index.tz is not None:
        now = now.tz_localize(ed.index.tz)
    elif now.tzinfo is not None and ed.index.tz is None:
        now = now.tz_localize(None)

    cutoff = now - pd.Timedelta(days=cfg["LOOKBACK_DAYS"])

    # Filter to past earnings only (date <= now) and within lookback
    past = ed[(ed.index <= now) & (ed.index >= cutoff)].copy()
    if past.empty:
        return None

    # Take the most recent one
    past = past.sort_index(ascending=False)
    row = past.iloc[0]
    earn_date = past.index[0]

    eps_actual = _float(row.get("Reported EPS"))
    eps_estimate = _float(row.get("EPS Estimate"))

    if eps_actual is None or eps_estimate is None:
        return None

    if abs(eps_estimate) < 0.001:
        surprise_pct = 0.0 if abs(eps_actual) < 0.001 else (100.0 if eps_actual > 0 else -100.0)
    else:
        surprise_pct = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100.0

    min_surp = cfg["MIN_SURPRISE_PCT"]
    reasons = []

    if surprise_pct >= min_surp:
        signal = "BUY"
        confidence = min(1.0, surprise_pct / 50.0) * 0.8
        reasons.append(f"Beat estimates by {surprise_pct:+.1f}%")
        reasons.append(f"EPS ${eps_actual:.2f} vs est ${eps_estimate:.2f}")
        reasons.append(f"Reported {earn_date.strftime('%Y-%m-%d')}")
    elif surprise_pct <= -min_surp:
        signal = "AVOID"
        confidence = min(1.0, abs(surprise_pct) / 50.0) * 0.8
        reasons.append(f"Missed estimates by {surprise_pct:+.1f}%")
        reasons.append(f"EPS ${eps_actual:.2f} vs est ${eps_estimate:.2f}")
    else:
        signal = "NEUTRAL"
        confidence = 0.1
        reasons.append(f"In-line earnings ({surprise_pct:+.1f}%)")

    return EarningsDriftSignal(
        ticker=ticker,
        signal=signal,
        surprise_pct=round(surprise_pct, 2),
        earnings_date=earn_date.strftime("%Y-%m-%d"),
        eps_actual=eps_actual,
        eps_estimate=eps_estimate,
        confidence=round(confidence, 3),
        reasons=reasons,
    )


def scan_earnings_universe(tickers: List[str], config: dict = None) -> List[EarningsDriftSignal]:
    """Scan a list of tickers for recent earnings surprises. Returns BUY/AVOID only."""
    results = []
    for tk in tickers:
        sig = analyze_earnings(tk, config)
        if sig and sig.signal in ("BUY", "AVOID"):
            results.append(sig)
    results.sort(key=lambda s: abs(s.surprise_pct), reverse=True)
    return results


def _float(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --- Backtesting helper ---

def get_historical_earnings(ticker: str, lookback_days: int = 730) -> pd.DataFrame:
    """Pull all historical earnings events for backtesting.
    Returns DataFrame with columns: date, eps_actual, eps_estimate, surprise_pct."""
    try:
        tk = yf.Ticker(ticker)
        ed = tk.earnings_dates
        if ed is None or ed.empty:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

    now = pd.Timestamp.now()
    if now.tzinfo is None and ed.index.tz is not None:
        now = now.tz_localize(ed.index.tz)

    cutoff = now - pd.Timedelta(days=lookback_days)
    past = ed[(ed.index <= now) & (ed.index >= cutoff)].copy()
    if past.empty:
        return pd.DataFrame()

    rows = []
    for dt, row in past.iterrows():
        actual = _float(row.get("Reported EPS"))
        est = _float(row.get("EPS Estimate"))
        if actual is None or est is None:
            continue
        if abs(est) < 0.001:
            surp = 0.0 if abs(actual) < 0.001 else (100.0 if actual > 0 else -100.0)
        else:
            surp = ((actual - est) / abs(est)) * 100.0
        rows.append({
            "date": dt.tz_localize(None) if hasattr(dt, "tz_localize") and dt.tzinfo else dt,
            "eps_actual": actual,
            "eps_estimate": est,
            "surprise_pct": surp,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sample = ["AAPL", "NVDA", "CRWD", "SOFI", "CELH", "TSLA", "CAVA"]
    for s in scan_earnings_universe(sample):
        print(f"  {s.ticker:6s}  {s.signal:5s}  surprise={s.surprise_pct:+.1f}%  "
              f"conf={s.confidence:.2f}  | {'; '.join(s.reasons[:2])}")
