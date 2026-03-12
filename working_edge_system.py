#!/usr/bin/env python3
"""
EDGE SYSTEM v2 - Rebuilt From Scratch
=====================================
Only outputs actionable trades. No noise, no maybes.

A trade is only generated when >= 3 independent signals confirm.
Every trade has: entry, stop loss, target, risk/reward, position size, exit date.

Signal layers (all free data):
  1. TREND      - Price vs 20/50 MA, golden cross
  2. MOMENTUM   - Relative strength vs SPY over 20 days
  3. VOLUME     - Unusual volume (accumulation/distribution)
  4. EARNINGS   - Post-earnings surprise drift (PEAD)
  5. ATTENTION  - Wikipedia pageview anomaly (path less travelled)
  6. SEC FILTER - Hard reject if going concern / material weakness

Minimum 3 of 5 signals must agree. SEC is a filter, not a signal.
"""
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trade output
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    ticker: str
    direction: str              # BUY or SHORT
    entry_price: float
    stop_loss: float
    target_price: float
    risk_pct: float             # stop distance as %
    reward_pct: float           # target distance as %
    risk_reward: float          # reward / risk
    position_pct: float         # suggested % of portfolio
    exit_date: str              # hold-until date
    conviction: int             # how many signals confirmed (3-5)
    signals: List[str]          # which signals fired
    reasons: List[str]          # human-readable explanation per signal
    scan_time: str
    signal_date: str

# ---------------------------------------------------------------------------
# Universe - tilted toward mid/small caps where signals actually matter
# ---------------------------------------------------------------------------

UNIVERSE = [
    # Mid-cap growth (less efficient, PEAD works better here)
    "CRWD", "DDOG", "NET", "ZS", "MDB", "HUBS", "DOCN", "GTLB",
    "CFLT", "PD", "BILL", "PCOR", "MNDY", "ESTC",
    # Fintech / disruptors
    "SOFI", "HOOD", "AFRM", "UPST", "LMND", "NU", "LC", "COIN",
    # Biotech / pharma (high earnings volatility = PEAD gold)
    "TGTX", "BMRN", "ALNY", "SRPT", "NBIX", "EXAS", "HALO",
    "LEGN", "BEAM", "CRSP", "NTLA", "PCVX",
    # Consumer growth
    "CELH", "CAVA", "ELF", "ONON", "CROX", "SHAK", "BROS", "DKS",
    # Industrials / infra
    "AXON", "BLDR", "GNRC", "STRL", "ATKR", "UFPI",
    # Energy / commodities
    "FANG", "MTDR", "AR", "RRC", "EQT", "CLF", "AA", "MP",
    # Space / frontier tech
    "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI",
    # High-beta / speculative (PEAD + attention signals strongest here)
    "FUBO", "PLUG", "CLOV", "LCID", "RIVN",
    # Clean energy
    "ENPH", "FSLR", "RUN",
    # Large cap (included for regime context, lower priority)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META",
    "AMD", "NFLX", "CRM", "UBER", "PLTR",
    # Misc momentum
    "JOBY", "ACHR", "RGTI", "RBLX", "MRNA", "BNTX", "PYPL",
    "IRM", "EQIX", "GME", "AMC",
]
UNIVERSE = list(dict.fromkeys(u.upper() for u in UNIVERSE))


# ---------------------------------------------------------------------------
# Signal 1: TREND (price action)
# ---------------------------------------------------------------------------

def check_trend(df: pd.DataFrame) -> Optional[dict]:
    """
    Check if stock is in a confirmed uptrend or downtrend.
    Requires price above both 20MA and 50MA for BUY.
    Returns dict with signal direction and details, or None.
    """
    if df is None or len(df) < 50:
        return None

    close = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma50 = df['Close'].rolling(50).mean().iloc[-1]

    if pd.isna(ma20) or pd.isna(ma50):
        return None

    above_20 = close > ma20
    above_50 = close > ma50
    golden = ma20 > ma50  # 20MA above 50MA

    if above_20 and above_50 and golden:
        return {
            "signal": "BUY",
            "reason": f"Uptrend: price ${close:.2f} > 20MA ${ma20:.2f} > 50MA ${ma50:.2f}",
            "strength": 1.0
        }
    elif above_20 and above_50:
        return {
            "signal": "BUY",
            "reason": f"Above both MAs: ${close:.2f} > 20MA ${ma20:.2f}, 50MA ${ma50:.2f}",
            "strength": 0.7
        }
    elif not above_20 and not above_50:
        return {
            "signal": "SHORT",
            "reason": f"Downtrend: ${close:.2f} < 20MA ${ma20:.2f} < 50MA ${ma50:.2f}",
            "strength": 0.8
        }
    return None


# ---------------------------------------------------------------------------
# Signal 2: MOMENTUM (relative strength vs SPY)
# ---------------------------------------------------------------------------

def check_momentum(df: pd.DataFrame, spy_df: pd.DataFrame) -> Optional[dict]:
    """
    Compare stock's 20-day return vs SPY's 20-day return.
    Outperformance = bullish momentum.
    """
    if df is None or spy_df is None or len(df) < 20 or len(spy_df) < 20:
        return None

    stock_return = (df['Close'].iloc[-1] / df['Close'].iloc[-20] - 1) * 100
    spy_return = (spy_df['Close'].iloc[-1] / spy_df['Close'].iloc[-20] - 1) * 100
    alpha = stock_return - spy_return

    if alpha > 5:
        return {
            "signal": "BUY",
            "reason": f"Strong RS: +{stock_return:.1f}% vs SPY +{spy_return:.1f}% (alpha +{alpha:.1f}%)",
            "strength": min(1.0, alpha / 15)
        }
    elif alpha < -8:
        return {
            "signal": "SHORT",
            "reason": f"Weak RS: {stock_return:+.1f}% vs SPY +{spy_return:.1f}% (alpha {alpha:+.1f}%)",
            "strength": min(1.0, abs(alpha) / 15)
        }
    return None


# ---------------------------------------------------------------------------
# Signal 3: VOLUME (unusual activity)
# ---------------------------------------------------------------------------

def check_volume(df: pd.DataFrame) -> Optional[dict]:
    """
    Detect unusual volume. Volume > 1.5x 20-day average on an up-day = accumulation.
    """
    if df is None or len(df) < 21:
        return None

    vol_today = df['Volume'].iloc[-1]
    vol_avg = df['Volume'].iloc[-21:-1].mean()

    if vol_avg <= 0:
        return None

    vol_ratio = vol_today / vol_avg
    price_change = (df['Close'].iloc[-1] / df['Close'].iloc[-2] - 1) * 100

    if vol_ratio > 1.5 and price_change > 0.5:
        return {
            "signal": "BUY",
            "reason": f"Volume surge {vol_ratio:.1f}x avg on +{price_change:.1f}% day (accumulation)",
            "strength": min(1.0, vol_ratio / 3)
        }
    elif vol_ratio > 1.5 and price_change < -0.5:
        return {
            "signal": "SHORT",
            "reason": f"Volume surge {vol_ratio:.1f}x avg on {price_change:.1f}% day (distribution)",
            "strength": min(1.0, vol_ratio / 3)
        }
    return None


# ---------------------------------------------------------------------------
# Signal 4: EARNINGS CATALYST (PEAD)
# ---------------------------------------------------------------------------

def check_earnings(ticker: str) -> Optional[dict]:
    """
    Check for recent earnings surprise > 10%. PEAD is strongest in first 40 days.
    Only fires if earnings were 1-15 days ago (entry delay).
    """
    try:
        tk = yf.Ticker(ticker)
        ed = tk.earnings_dates
        if ed is None or ed.empty:
            return None
    except Exception:
        return None

    now = pd.Timestamp.now()
    if ed.index.tz is not None and now.tzinfo is None:
        now = now.tz_localize(ed.index.tz)

    cutoff = now - pd.Timedelta(days=15)
    past = ed[(ed.index <= now) & (ed.index >= cutoff)]
    if past.empty:
        return None

    past = past.sort_index(ascending=False)
    row = past.iloc[0]
    earn_date = past.index[0]

    # Must be at least 1 day old (entry delay)
    if (now - earn_date).days < 1:
        return None

    eps_actual = _safe_float(row.get("Reported EPS"))
    eps_estimate = _safe_float(row.get("EPS Estimate"))
    if eps_actual is None or eps_estimate is None:
        return None

    if abs(eps_estimate) < 0.001:
        surprise = 100.0 if eps_actual > 0 else -100.0
    else:
        surprise = ((eps_actual - eps_estimate) / abs(eps_estimate)) * 100

    days_since = (now - earn_date).days

    if surprise >= 10:
        return {
            "signal": "BUY",
            "reason": f"Earnings beat +{surprise:.1f}% ({days_since}d ago) EPS ${eps_actual:.2f} vs est ${eps_estimate:.2f}",
            "strength": min(1.0, surprise / 40)
        }
    elif surprise <= -10:
        return {
            "signal": "SHORT",
            "reason": f"Earnings miss {surprise:.1f}% ({days_since}d ago) EPS ${eps_actual:.2f} vs est ${eps_estimate:.2f}",
            "strength": min(1.0, abs(surprise) / 40)
        }
    return None


# ---------------------------------------------------------------------------
# Signal 5: ATTENTION ANOMALY (Wikipedia - path less travelled)
# ---------------------------------------------------------------------------

def check_attention(ticker: str) -> Optional[dict]:
    """
    Wikipedia pageview spike detection. Rising attention on an
    otherwise quiet stock can precede moves.
    """
    try:
        import wikipedia_views
        score = wikipedia_views.trend_score(ticker, 14)
        if score is None:
            return None

        if score > 0.5:
            return {
                "signal": "BUY",
                "reason": f"Wikipedia attention surging (score {score:+.2f})",
                "strength": min(1.0, score)
            }
        elif score < -0.5:
            return {
                "signal": "SHORT",
                "reason": f"Wikipedia attention collapsing (score {score:+.2f})",
                "strength": min(1.0, abs(score))
            }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Filter: SEC FILING RISK (hard reject)
# ---------------------------------------------------------------------------

def check_sec_risk(ticker: str) -> bool:
    """Returns True if clean (no risk phrases). False = REJECT."""
    try:
        import sec_filing_risk
        clean, form, risk_count = sec_filing_risk.is_clean(ticker, {})
        if not clean:
            logger.debug(f"SEC REJECT {ticker}: {risk_count} risk phrases in {form}")
        return clean
    except Exception:
        return True  # if we can't check, don't block


# ---------------------------------------------------------------------------
# Trade calculation
# ---------------------------------------------------------------------------

def calculate_trade(
    ticker: str,
    direction: str,
    df: pd.DataFrame,
    conviction: int,
    signals: List[str],
    reasons: List[str],
    hold_days: int = 30,
) -> Optional[Trade]:
    """
    Calculate complete trade with entry, stop, target, position size.
    """
    if df is None or len(df) < 20:
        return None

    entry = float(df['Close'].iloc[-1])
    if entry <= 0:
        return None

    # ATR for stop calculation (14-period)
    high = df['High'].values[-14:]
    low = df['Low'].values[-14:]
    close_prev = df['Close'].values[-15:-1]
    tr = np.maximum(high - low, np.maximum(abs(high - close_prev), abs(low - close_prev)))
    atr = float(np.mean(tr))

    if atr <= 0:
        return None

    if direction == "BUY":
        # Stop: 2x ATR below entry, or recent swing low (whichever is tighter but not too tight)
        swing_low = float(df['Low'].iloc[-10:].min())
        atr_stop = entry - (2.0 * atr)
        stop = max(atr_stop, swing_low)  # use whichever is higher (tighter)

        # Don't take trade if stop is too far (> 8%) or too tight (< 1%)
        risk_pct = (entry - stop) / entry * 100
        if risk_pct > 8 or risk_pct < 1:
            stop = entry * 0.95  # default 5% stop
            risk_pct = 5.0

        # Target: minimum 1.5:1 R:R, scale with conviction
        rr_target = 1.5 + (conviction - 3) * 0.5  # 3 signals=1.5, 4=2.0, 5=2.5
        target = entry + (entry - stop) * rr_target

        reward_pct = (target - entry) / entry * 100

    else:  # SHORT
        swing_high = float(df['High'].iloc[-10:].max())
        atr_stop = entry + (2.0 * atr)
        stop = min(atr_stop, swing_high)

        risk_pct = (stop - entry) / entry * 100
        if risk_pct > 8 or risk_pct < 1:
            stop = entry * 1.05
            risk_pct = 5.0

        rr_target = 1.5 + (conviction - 3) * 0.5
        target = entry - (stop - entry) * rr_target

        reward_pct = (entry - target) / entry * 100

    risk_reward = reward_pct / risk_pct if risk_pct > 0 else 0

    # Position sizing: risk 2% of portfolio per trade
    # position_pct = 2% / risk_pct (so if risk is 5%, position = 40% ... cap at 10%)
    position_pct = min(10.0, (2.0 / risk_pct) * 100) if risk_pct > 0 else 2.0

    exit_date = (datetime.now() + timedelta(days=hold_days)).strftime('%Y-%m-%d')
    now = datetime.now()

    return Trade(
        ticker=ticker,
        direction=direction,
        entry_price=round(entry, 2),
        stop_loss=round(stop, 2),
        target_price=round(target, 2),
        risk_pct=round(risk_pct, 1),
        reward_pct=round(reward_pct, 1),
        risk_reward=round(risk_reward, 1),
        position_pct=round(position_pct, 1),
        exit_date=exit_date,
        conviction=conviction,
        signals=signals,
        reasons=reasons,
        scan_time=now.strftime('%H:%M:%S'),
        signal_date=now.strftime('%Y-%m-%d'),
    )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class EdgeSystem:
    """
    Multi-factor edge detection. Only outputs trades when >= 3 signals confirm.
    """

    def __init__(self, min_conviction: int = 3):
        self.min_conviction = min_conviction
        self._spy_cache = None

    def _get_spy(self) -> Optional[pd.DataFrame]:
        if self._spy_cache is not None:
            return self._spy_cache
        try:
            spy = yf.Ticker("SPY")
            df = spy.history(period="6mo")
            if df is not None and not df.empty:
                df.index = df.index.tz_localize(None) if df.index.tz else df.index
                self._spy_cache = df
                return df
        except Exception:
            pass
        return None

    def analyze(self, ticker: str) -> Optional[Trade]:
        """
        Run all signal layers on a ticker.
        Returns a Trade only if >= min_conviction signals agree on direction.
        """
        # Get price data
        try:
            tk = yf.Ticker(ticker)
            df = tk.history(period="6mo")
            if df is None or len(df) < 50:
                return None
            df.index = df.index.tz_localize(None) if df.index.tz else df.index
        except Exception:
            return None

        spy_df = self._get_spy()

        # SEC filter first - hard reject
        if not check_sec_risk(ticker):
            return None

        # Collect signals
        buy_signals = []
        buy_reasons = []
        short_signals = []
        short_reasons = []

        # 1. Trend
        trend = check_trend(df)
        if trend:
            if trend['signal'] == 'BUY':
                buy_signals.append('TREND')
                buy_reasons.append(trend['reason'])
            else:
                short_signals.append('TREND')
                short_reasons.append(trend['reason'])

        # 2. Momentum (relative strength)
        momentum = check_momentum(df, spy_df)
        if momentum:
            if momentum['signal'] == 'BUY':
                buy_signals.append('MOMENTUM')
                buy_reasons.append(momentum['reason'])
            else:
                short_signals.append('MOMENTUM')
                short_reasons.append(momentum['reason'])

        # 3. Volume
        volume = check_volume(df)
        if volume:
            if volume['signal'] == 'BUY':
                buy_signals.append('VOLUME')
                buy_reasons.append(volume['reason'])
            else:
                short_signals.append('VOLUME')
                short_reasons.append(volume['reason'])

        # 4. Earnings
        earnings = check_earnings(ticker)
        if earnings:
            if earnings['signal'] == 'BUY':
                buy_signals.append('EARNINGS')
                buy_reasons.append(earnings['reason'])
            else:
                short_signals.append('EARNINGS')
                short_reasons.append(earnings['reason'])

        # 5. Attention (Wikipedia)
        attention = check_attention(ticker)
        if attention:
            if attention['signal'] == 'BUY':
                buy_signals.append('ATTENTION')
                buy_reasons.append(attention['reason'])
            else:
                short_signals.append('ATTENTION')
                short_reasons.append(attention['reason'])

        # Check if enough signals agree
        if len(buy_signals) >= self.min_conviction:
            return calculate_trade(
                ticker=ticker,
                direction="BUY",
                df=df,
                conviction=len(buy_signals),
                signals=buy_signals,
                reasons=buy_reasons,
            )
        elif len(short_signals) >= self.min_conviction:
            return calculate_trade(
                ticker=ticker,
                direction="SHORT",
                df=df,
                conviction=len(short_signals),
                signals=short_signals,
                reasons=short_reasons,
            )

        return None

    def scan(self, tickers: List[str] = None) -> List[Trade]:
        """Scan universe for actionable trades."""
        tickers = tickers or UNIVERSE
        trades = []

        logger.info(f"Scanning {len(tickers)} tickers (min conviction: {self.min_conviction})...")

        for i, ticker in enumerate(tickers, 1):
            if i % 20 == 0:
                logger.info(f"  Progress: {i}/{len(tickers)}")

            try:
                trade = self.analyze(ticker)
                if trade:
                    trades.append(trade)
                    logger.info(f"  >> TRADE: {trade.direction} {trade.ticker} @ ${trade.entry_price}")
            except Exception as e:
                logger.debug(f"Error analyzing {ticker}: {e}")

            # Rate limit yfinance
            time.sleep(0.3)

        # Sort: highest conviction first, then by risk/reward
        trades.sort(key=lambda t: (t.conviction, t.risk_reward), reverse=True)
        return trades


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        val = float(v)
        return None if pd.isna(val) else val
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    system = EdgeSystem(min_conviction=3)
    trades = system.scan()

    print(f"\n{'='*70}")
    print(f"  TRADES FOUND: {len(trades)}")
    print(f"{'='*70}")

    if not trades:
        print("\n  No trades meet the conviction threshold.")
        print("  This is normal - the system is selective by design.")
    else:
        for t in trades:
            print(f"\n  {'BUY' if t.direction == 'BUY' else 'SHORT'} {t.ticker} @ ${t.entry_price}")
            print(f"  Stop: ${t.stop_loss} ({t.risk_pct}%)")
            print(f"  Target: ${t.target_price} ({t.reward_pct}%)")
            print(f"  R:R {t.risk_reward} | Position: {t.position_pct}% portfolio")
            print(f"  Exit by: {t.exit_date}")
            print(f"  Conviction: {t.conviction}/5 signals")
            for r in t.reasons:
                print(f"    - {r}")

    print(f"\n{'='*70}")
