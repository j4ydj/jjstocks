#!/usr/bin/env python3
"""
EDGE SYSTEM v2 - Rebuilt From Scratch
=====================================
Only outputs actionable trades. No noise, no maybes.

A trade is only generated when >= 3 independent signals confirm.
Every trade has: entry, stop loss, target, risk/reward, position size, exit date.

Signal layers (all free data):
  1. TREND      - Price vs 20/50 MA, golden cross
  2. MOMENTUM   - Relative strength vs SPY over ~3 months (63 days)
  3. VOLUME     - Unusual volume (accumulation/distribution)
  4. EARNINGS   - PEAD: EPS surprise >10% AND stock closed in direction on announcement day
  5. ATTENTION  - StockTwits trader sentiment (not Wikipedia)
  SEC FILTER    - Off by default (set USE_SEC_FILTER=1 to enable).

R:R fixed at 2:1. Position risk: 1.5% (3 sig), 2% (4 sig), 2.5% (5 sig). Gap rule: cancel if open >1% from entry.
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
    slippage_pct: float = 1.0   # do not enter if price moved > this % from entry (gap rule)

# ---------------------------------------------------------------------------
# Universe: S&P 500 + extras (liquid names not in index)
# ---------------------------------------------------------------------------

import os as _os

def _load_universe() -> List[str]:
    """Load ticker list: S&P 500 from sp500_symbols.txt, plus extras not in index."""
    base = _os.path.dirname(_os.path.abspath(__file__))
    path = _os.path.join(base, "sp500_symbols.txt")
    tickers = []
    if _os.path.exists(path):
        with open(path) as f:
            for line in f:
                s = line.strip().upper()
                if s and not s.startswith("#"):
                    tickers.append(s)
    extras = [
        "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI",
        "GME", "AMC", "JOBY", "ACHR", "RGTI",
    ]
    for t in extras:
        if t not in tickers:
            tickers.append(t)
    return list(dict.fromkeys(tickers))

UNIVERSE = _load_universe()


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
    Compare stock's ~3-month return vs SPY (63 trading days).
    Aligns with momentum factor and 30-day hold period.
    """
    window = 63  # ~3 months
    if df is None or spy_df is None or len(df) < window or len(spy_df) < window:
        return None

    stock_return = (df['Close'].iloc[-1] / df['Close'].iloc[-window] - 1) * 100
    spy_return = (spy_df['Close'].iloc[-1] / spy_df['Close'].iloc[-window] - 1) * 100
    alpha = stock_return - spy_return

    if alpha > 5:
        return {
            "signal": "BUY",
            "reason": f"Strong RS (3m): +{stock_return:.1f}% vs SPY +{spy_return:.1f}% (alpha +{alpha:.1f}%)",
            "strength": min(1.0, alpha / 15)
        }
    elif alpha < -8:
        return {
            "signal": "SHORT",
            "reason": f"Weak RS (3m): {stock_return:+.1f}% vs SPY +{spy_return:.1f}% (alpha {alpha:+.1f}%)",
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
# Signal 4: EARNINGS CATALYST (PEAD) + price reaction
# ---------------------------------------------------------------------------

def check_earnings(ticker: str, df: pd.DataFrame) -> Optional[dict]:
    """
    Earnings surprise > 10% AND stock closed in the right direction on announcement day.
    BUY only if beat AND close > prior close; SHORT only if miss AND close < prior close.
    Confirms institutional agreement with the print.

    Note: yfinance earnings_dates / Reported EPS / EPS Estimate are flaky (often empty or delayed).
    Expect EARNINGS to fire rarely. For production, consider AlphaVantage or Financial Modeling Prep (FMP).
    """
    try:
        tk = yf.Ticker(ticker)
        ed = tk.earnings_dates
        if ed is None or ed.empty:
            return None
    except Exception:
        return None

    if df is None or len(df) < 5:
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

    # Price reaction: did stock close higher (BUY) or lower (SHORT) on announcement day?
    try:
        earn_dt = (earn_date.to_pydatetime().date() if hasattr(earn_date, "to_pydatetime")
                   else earn_date.date() if hasattr(earn_date, "date") else earn_date)
        idx_ann = None
        for i in range(len(df)):
            row_date = df.index[i]
            row_d = row_date.date() if hasattr(row_date, "date") else row_date
            if row_d >= earn_dt:
                idx_ann = i
                break
        if idx_ann is None or idx_ann < 1:
            return None
        close_ann = float(df["Close"].iloc[idx_ann])
        close_prev = float(df["Close"].iloc[idx_ann - 1])
        closed_higher = close_ann > close_prev
        closed_lower = close_ann < close_prev
    except Exception:
        return None

    days_since = (now - earn_date).days

    if surprise >= 10 and closed_higher:
        return {
            "signal": "BUY",
            "reason": f"Earnings beat +{surprise:.1f}% ({days_since}d ago), stock closed up on announcement (institutional confirmation)",
            "strength": min(1.0, surprise / 40)
        }
    elif surprise <= -10 and closed_lower:
        return {
            "signal": "SHORT",
            "reason": f"Earnings miss {surprise:.1f}% ({days_since}d ago), stock closed down on announcement (institutional confirmation)",
            "strength": min(1.0, abs(surprise) / 40)
        }
    return None


# ---------------------------------------------------------------------------
# Signal 5: ATTENTION (trader chatter — StockTwits)
# ---------------------------------------------------------------------------

def check_attention(ticker: str) -> Optional[dict]:
    """
    StockTwits symbol stream: trader sentiment. BUY if bullish buzz, SHORT if bearish.
    Trader attention, not general web (e.g. homework on Microsoft).
    """
    try:
        import trader_attention
        score = trader_attention.trend_score(ticker)
        if score is None:
            return None

        if score > 0.5:
            return {
                "signal": "BUY",
                "reason": f"Trader buzz bullish (StockTwits score {score:+.2f})",
                "strength": min(1.0, score)
            }
        elif score < -0.5:
            return {
                "signal": "SHORT",
                "reason": f"Trader buzz bearish (StockTwits score {score:+.2f})",
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

        # Target: static 2:1 R:R for all trades (mathematically sound)
        rr_target = 2.0
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

        rr_target = 2.0
        target = entry - (stop - entry) * rr_target

        reward_pct = (entry - target) / entry * 100

    risk_reward = reward_pct / risk_pct if risk_pct > 0 else 0

    # Position sizing: conviction-based portfolio risk (1.5% / 2% / 2.5%).
    # Formula: position_pct = (portfolio_risk_pct / risk_pct) * 100 so that if stopped out we lose portfolio_risk_pct.
    # Cap at 30% so we can actually reach 2% portfolio risk when stop is ~7% (2/7*100 ≈ 28.5%).
    portfolio_risk_pct = {3: 1.5, 4: 2.0, 5: 2.5}.get(conviction, 2.0)
    position_pct = min(30.0, (portfolio_risk_pct / risk_pct) * 100) if risk_pct > 0 else 2.0

    exit_date = (datetime.now() + timedelta(days=hold_days)).strftime('%Y-%m-%d')
    now = datetime.now()
    slippage_pct = 1.0  # gap rule: cancel or recalc if open > 1% away from entry

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
        slippage_pct=slippage_pct,
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

    def analyze(
        self,
        ticker: str,
        df: Optional[pd.DataFrame] = None,
        spy_df: Optional[pd.DataFrame] = None,
    ) -> Optional[Trade]:
        """
        Run all signal layers on a ticker.
        Returns a Trade only if >= min_conviction signals agree on direction.
        If df/spy_df are provided (e.g. from bulk download), they are used; otherwise fetched per ticker.
        """
        # Use provided price data or fetch
        if df is None:
            try:
                tk = yf.Ticker(ticker)
                df = tk.history(period="6mo")
                if df is None or len(df) < 63:
                    return None
                df.index = df.index.tz_localize(None) if df.index.tz else df.index
            except Exception:
                return None
        else:
            if len(df) < 63:
                return None

        if spy_df is None:
            spy_df = self._get_spy()

        # SEC filter: optional (set USE_SEC_FILTER=1 to enable). Off by default for S&P 500 + 2% stops.
        if _os.environ.get("USE_SEC_FILTER", "").strip() == "1" and not check_sec_risk(ticker):
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
        earnings = check_earnings(ticker, df)
        if earnings:
            if earnings['signal'] == 'BUY':
                buy_signals.append('EARNINGS')
                buy_reasons.append(earnings['reason'])
            else:
                short_signals.append('EARNINGS')
                short_reasons.append(earnings['reason'])

        # 5. Attention (StockTwits)
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
        """Scan universe for actionable trades. Bulk-downloads price data first for speed."""
        tickers = list(tickers or UNIVERSE)
        trades = []

        logger.info(f"Scanning {len(tickers)} tickers (min conviction: {self.min_conviction})...")

        # Bulk-download all price data in one call (~5 sec for 500+ tickers)
        prefetched: Dict[str, pd.DataFrame] = {}
        spy_df: Optional[pd.DataFrame] = None
        try:
            syms = tickers + ["SPY"]
            raw = yf.download(
                syms,
                period="6mo",
                group_by="ticker",
                progress=False,
                threads=True,
                auto_adjust=True,
            )
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    ticker_cols = raw.columns.get_level_values(0).unique()
                    if "SPY" in ticker_cols:
                        spy_df = raw["SPY"].copy()
                        if spy_df.index.tz is not None:
                            spy_df.index = spy_df.index.tz_localize(None)
                    for t in tickers:
                        if t in ticker_cols:
                            df_t = raw[t].copy()
                            if df_t.index.tz is not None:
                                df_t.index = df_t.index.tz_localize(None)
                            if len(df_t) >= 63 and "Close" in df_t.columns:
                                prefetched[t] = df_t
                else:
                    # Single-ticker result (e.g. one symbol)
                    if len(tickers) == 1 and len(raw) >= 63:
                        if raw.index.tz is not None:
                            raw = raw.copy()
                            raw.index = raw.index.tz_localize(None)
                        prefetched[tickers[0]] = raw
        except Exception as e:
            logger.warning("Bulk download failed, falling back to per-ticker fetch: %s", e)

        for i, ticker in enumerate(tickers, 1):
            if i % 50 == 0:
                logger.info(f"  Progress: {i}/{len(tickers)}")

            try:
                df = prefetched.get(ticker)
                if df is None:
                    time.sleep(0.3)  # rate limit when we have to fetch this ticker in analyze()
                trade = self.analyze(ticker, df=df, spy_df=spy_df)
                if trade:
                    trades.append(trade)
                    logger.info(f"  >> TRADE: {trade.direction} {trade.ticker} @ ${trade.entry_price}")
            except Exception as e:
                logger.debug(f"Error analyzing {ticker}: {e}")

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
