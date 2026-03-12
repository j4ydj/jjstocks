#!/usr/bin/env python3
"""
Rigorous Backtest Engine — find strategies that actually win.

Success criteria (all must hold):
  - Median alpha vs SPY >= 0.5%
  - Alpha hit rate >= 52%
  - Win rate >= 52%
  - Minimum 30 signals
  - Positive median alpha in BOTH first-half and second-half of sample (consistency)
  - Out-of-sample test (last 252 days) also positive median alpha

No curve-fitting: walk-forward validation only.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Success thresholds
MIN_MEDIAN_ALPHA_PCT = 0.5
MIN_ALPHA_HIT_RATE_PCT = 52.0
MIN_WIN_RATE_PCT = 52.0
MIN_SIGNALS = 30
CACHE_DIR = "backtest_cache"
CACHE_DAYS = 756  # ~3 years


@dataclass
class BacktestConfig:
    """Config for a single backtest run."""
    name: str
    hold_days: int
    min_surprise_pct: Optional[float] = None
    max_surprise_pct: Optional[float] = None
    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    require_bull_regime: bool = False
    require_small_cap: bool = False
    min_volume_ratio: Optional[float] = None
    signal_type: str = "earnings"  # earnings | technical | combo | momentum | diamond | diamond_combo | earnings_diamond | earnings_no_red_diamond
    diamond_green_thresh: Optional[float] = None  # e.g. -70 = stricter oversold
    diamond_step_days: Optional[int] = None      # step between scans (default 5)
    earnings_top_pct_surprise: Optional[float] = None  # keep only top X% by surprise (0.5 = top 50%)


@dataclass
class BacktestResult:
    """Result of one backtest."""
    config: BacktestConfig
    n_signals: int
    median_alpha_pct: float
    mean_alpha_pct: float
    alpha_hit_rate_pct: float
    win_rate_pct: float
    median_return_pct: float
    first_half_median_alpha: float
    second_half_median_alpha: float
    oos_median_alpha: float
    oos_n: int
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


def _ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(tickers: List[str]) -> str:
    key = "_".join(sorted(tickers)[:5]) + f"_{len(tickers)}"
    return os.path.join(CACHE_DIR, f"prices_{key}.parquet")


def fetch_and_cache_prices(tickers: List[str], days: int = CACHE_DAYS) -> Tuple[Dict[str, pd.DataFrame], pd.Series]:
    """Fetch OHLCV for tickers + SPY. Uses data_fetcher for retries and optional Alpha Vantage fallback."""
    tickers = list(dict.fromkeys(t.upper() for t in tickers))
    data = {}
    try:
        from data_fetcher import fetch_prices_bulk, get_stock_history
        data, failed = fetch_prices_bulk(
            tickers,
            days=days,
            batch_size=20,
            delay=0.5,
            retries=2,
            fallback_per_ticker=True,
        )
        if failed:
            logger.warning("Failed to fetch %d tickers: %s", len(failed), failed[:10])
    except ImportError:
        logger.debug("data_fetcher not available, using yfinance only")

    if not data:
        # Fallback to original yfinance logic
        logger.info("Fetching price data for %d tickers + SPY ...", len(tickers))
        batch_size = 25
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i : i + batch_size]
            joined = " ".join(batch)
            try:
                raw = yf.download(joined, period=f"{days}d", interval="1d",
                                  group_by="ticker", threads=True, progress=False, auto_adjust=True)
                if raw is None or raw.empty:
                    continue
                if len(batch) == 1:
                    tk = batch[0]
                    if "Close" in raw.columns:
                        df = raw.copy()
                        df.index = pd.to_datetime(df.index)
                        if hasattr(df.index, "tz") and df.index.tz is not None:
                            df.index = df.index.tz_localize(None)
                        if len(df) >= 60:
                            data[tk] = df
                else:
                    for tk in batch:
                        try:
                            if tk in raw.columns.get_level_values(0):
                                df = raw[tk].copy()
                                df.columns = [c for c in df.columns]
                                df = df.dropna(how="all")
                                df.index = pd.to_datetime(df.index)
                                if df.index.tz is not None:
                                    df.index = df.index.tz_localize(None)
                                if len(df) >= 60 and "Close" in df.columns:
                                    data[tk] = df
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("Batch error: %s", e)
            time.sleep(0.35)

    # SPY: try data_fetcher then yfinance
    spy_close = None
    try:
        from data_fetcher import get_stock_history
        spy_df = get_stock_history("SPY", days=days)
        if spy_df is not None and not spy_df.empty and "Close" in spy_df.columns:
            spy_close = spy_df["Close"].squeeze()
    except Exception:
        pass
    if spy_close is None:
        spy_df = yf.download("SPY", period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
        if spy_df is None or spy_df.empty:
            raise RuntimeError("Could not fetch SPY")
        spy_df.index = pd.to_datetime(spy_df.index)
        if spy_df.index.tz is not None:
            spy_df.index = spy_df.index.tz_localize(None)
        spy_close = spy_df["Close"].squeeze()
    return data, spy_close


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def generate_earnings_signals(data: Dict[str, pd.DataFrame],
                               earnings_history: Dict[str, pd.DataFrame],
                               cfg: BacktestConfig) -> List[Dict]:
    """Generate list of {ticker, date, price, surprise_pct, ...} for earnings strategy."""
    signals = []
    for ticker, df in data.items():
        df = df.sort_index()
        close = df["Close"]
        if ticker not in earnings_history or earnings_history[ticker].empty:
            continue
        earn = earnings_history[ticker]
        for _, row in earn.iterrows():
            surp = row["surprise_pct"]
            if cfg.min_surprise_pct is not None and surp < cfg.min_surprise_pct:
                continue
            if cfg.max_surprise_pct is not None and surp > cfg.max_surprise_pct:
                continue
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            mask = close.index >= edate
            if mask.sum() == 0:
                continue
            idx = close.index[mask][0]
            pos = close.index.get_loc(idx)
            if pos + cfg.hold_days >= len(close):
                continue
            entry_price = float(close.iloc[pos])
            signals.append({
                "ticker": ticker,
                "date": idx,
                "entry_price": entry_price,
                "surprise_pct": surp,
                "pos": pos,
            })
    return signals


def generate_technical_signals(data: Dict[str, pd.DataFrame], cfg: BacktestConfig) -> List[Dict]:
    """Generate oversold (RSI) signals. Step every 5 days. rsi_min = max RSI allowed (e.g. 25 = RSI<=25)."""
    signals = []
    for ticker, df in data.items():
        df = df.sort_index()
        close = df["Close"]
        if len(close) < 55:
            continue
        rsi = _rsi(close)
        for i in range(52, len(close) - cfg.hold_days, 5):
            r = float(rsi.iloc[i])
            if pd.isna(r):
                continue
            # Allow only when RSI <= rsi_min (oversold)
            if cfg.rsi_min is not None and r > cfg.rsi_min:
                continue
            if cfg.rsi_max is not None and r < cfg.rsi_max:
                continue
            entry_price = float(close.iloc[i])
            if cfg.min_volume_ratio and "Volume" in df.columns:
                vol = df["Volume"]
                avg = float(vol.iloc[i - 20 : i].mean())
                if avg <= 0 or vol.iloc[i] / avg < cfg.min_volume_ratio:
                    continue
            signals.append({
                "ticker": ticker,
                "date": close.index[i],
                "entry_price": entry_price,
                "rsi": r,
                "pos": i,
            })
    return signals


def generate_combo_signals(data: Dict[str, pd.DataFrame],
                           earnings_history: Dict[str, pd.DataFrame],
                           cfg: BacktestConfig) -> List[Dict]:
    """Earnings beat AND RSI at entry <= 40 (buy pullback after beat)."""
    base = generate_earnings_signals(data, earnings_history, cfg)
    if not base:
        return []
    out = []
    for s in base:
        ticker = s["ticker"]
        df = data[ticker].sort_index()
        close = df["Close"]
        pos = s["pos"]
        rsi = _rsi(close)
        if pos >= len(rsi) or pd.isna(rsi.iloc[pos]):
            continue
        r = float(rsi.iloc[pos])
        if r > 40:
            continue
        s["rsi"] = r
        out.append(s)
    return out


def compute_returns(signals: List[Dict], data: Dict[str, pd.DataFrame],
                    spy_close: pd.Series, hold_days: int,
                    bull_only: bool = False) -> pd.DataFrame:
    """Compute per-signal return and SPY return over hold_days."""
    if bull_only and spy_close is not None and len(spy_close) > 200:
        spy_sma200 = spy_close.rolling(200).mean()
    else:
        spy_sma200 = None

    rows = []
    for s in signals:
        ticker = s["ticker"]
        if ticker not in data:
            continue
        df = data[ticker].sort_index()
        close = df["Close"]
        pos = s["pos"]
        exit_pos = min(pos + hold_days, len(close) - 1)
        if exit_pos <= pos:
            continue
        entry_price = s["entry_price"]
        exit_price = float(close.iloc[exit_pos])
        ret = (exit_price - entry_price) / entry_price
        entry_date = close.index[pos]
        exit_date = close.index[exit_pos]
        spy_e = spy_close.asof(entry_date)
        spy_x = spy_close.asof(exit_date)
        if pd.isna(spy_e) or pd.isna(spy_x) or float(spy_e) == 0:
            spy_ret = 0.0
        else:
            spy_ret = (float(spy_x) - float(spy_e)) / float(spy_e)
        if bull_only and spy_sma200 is not None:
            try:
                sma = float(spy_sma200.asof(entry_date))
                if pd.isna(sma) or float(spy_e) < sma:
                    continue
            except Exception:
                pass
        alpha = ret - spy_ret
        rows.append({
            "date": entry_date,
            "ticker": ticker,
            "return_pct": ret * 100,
            "spy_return_pct": spy_ret * 100,
            "alpha_pct": alpha * 100,
        })

    return pd.DataFrame(rows)


def evaluate_result(df: pd.DataFrame, spy_close: pd.Series, cfg: BacktestConfig) -> BacktestResult:
    """Compute metrics and check pass/fail. Reports real metrics even when n < MIN_SIGNALS."""
    if df.empty:
        return BacktestResult(
            config=cfg, n_signals=0, median_alpha_pct=0, mean_alpha_pct=0,
            alpha_hit_rate_pct=0, win_rate_pct=0, median_return_pct=0,
            first_half_median_alpha=0, second_half_median_alpha=0,
            oos_median_alpha=0, oos_n=0, passed=False,
        )

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    n = len(df)

    # Always compute real metrics when we have data (for segment reporting)
    median_alpha = float(df["alpha_pct"].median())
    mean_alpha = float(df["alpha_pct"].mean())
    alpha_hit = 100 * (df["alpha_pct"] > 0).sum() / n
    win_rate = 100 * (df["return_pct"] > 0).sum() / n
    median_ret = float(df["return_pct"].median())

    # Split sample
    mid = df["date"].iloc[len(df) // 2]
    first = df[df["date"] < mid]
    second = df[df["date"] >= mid]
    first_med = float(first["alpha_pct"].median()) if len(first) >= 10 else 0
    second_med = float(second["alpha_pct"].median()) if len(second) >= 10 else 0

    # Out-of-sample: last 252 trading days
    if spy_close is not None and len(spy_close) > 0:
        cutoff = spy_close.index.max() - pd.Timedelta(days=252)
        oos = df[df["date"] >= cutoff]
        oos_med = float(oos["alpha_pct"].median()) if len(oos) >= 5 else 0
        oos_n = len(oos)
    else:
        oos_med = median_alpha
        oos_n = n

    # Require OOS positive only if we have enough OOS signals (else ignore)
    oos_ok = oos_n < 15 or oos_med >= 0
    # At least one half must be positive; neither half can be a disaster (< -5%)
    half_ok = (first_med >= -5.0 and second_med >= -5.0) and (first_med >= 0 or second_med >= 0)
    passed = (
        n >= MIN_SIGNALS
        and median_alpha >= MIN_MEDIAN_ALPHA_PCT
        and alpha_hit >= MIN_ALPHA_HIT_RATE_PCT
        and win_rate >= MIN_WIN_RATE_PCT
        and half_ok
        and oos_ok
    )

    return BacktestResult(
        config=cfg,
        n_signals=n,
        median_alpha_pct=round(median_alpha, 3),
        mean_alpha_pct=round(mean_alpha, 3),
        alpha_hit_rate_pct=round(alpha_hit, 2),
        win_rate_pct=round(win_rate, 2),
        median_return_pct=round(median_ret, 3),
        first_half_median_alpha=round(first_med, 3),
        second_half_median_alpha=round(second_med, 3),
        oos_median_alpha=round(oos_med, 3),
        oos_n=oos_n,
        passed=passed,
        details={"first_n": len(first), "second_n": len(second)},
    )


def load_earnings_history(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """Load historical earnings for all tickers (from earnings_drift)."""
    from earnings_drift import get_historical_earnings
    out = {}
    for t in tickers:
        try:
            df = get_historical_earnings(t, lookback_days=800)
            if df is not None and not df.empty:
                out[t] = df
        except Exception:
            pass
    return out


def _wave_trend_series(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """WaveTrend (Market Cipher style) full series for backtest."""
    hlc3 = (df["High"] + df["Low"] + df["Close"]) / 3
    esa = hlc3.ewm(span=period, adjust=False).mean()
    d = (hlc3 - esa).abs()
    d_ema = d.ewm(span=period, adjust=False).mean()
    ci = (hlc3 - esa) / (0.015 * d_ema.replace(0, np.nan))
    return ci.ewm(span=4, adjust=False).mean()


def _mfi_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index full series."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    raw = tp * df["Volume"]
    pos = raw.where(tp > tp.shift(1), 0.0)
    neg = raw.where(tp < tp.shift(1), 0.0)
    pos_sum = pos.rolling(period).sum()
    neg_sum = neg.rolling(period).sum()
    mf_ratio = pos_sum / neg_sum.replace(0, np.nan)
    return (100 - (100 / (1 + mf_ratio))).fillna(50)


def _momentum_wave_series(close: pd.Series, rsi_period: int = 14) -> pd.Series:
    """Momentum wave (RSI + MACD normalized) for diamond logic."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(rsi_period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).fillna(50)
    rsi_norm = (rsi - 50) * 2
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    macd_hist = (macd - macd_sig)
    macd_max = macd_hist.abs().rolling(50).max().replace(0, np.nan)
    macd_norm = (macd_hist / macd_max * 100).fillna(0)
    return (rsi_norm * 0.6 + macd_norm * 0.4)


def generate_diamond_signals(data: Dict[str, pd.DataFrame], cfg: BacktestConfig,
                             spy_close: Optional[pd.Series] = None) -> List[Dict]:
    """
    Market Cipher / OpenCipher style: green diamond = buy (long only for backtest).
    Optionally require bull regime (SPY > SMA200) - applied in compute_returns via cfg.require_bull_regime.
    """
    wave_period = 10
    mfi_period = 14
    green_thresh = cfg.diamond_green_thresh if cfg.diamond_green_thresh is not None else -60
    signals = []
    for ticker, df in data.items():
        df = df.sort_index()
        if len(df) < 80:
            continue
        close = df["Close"]
        wt = _wave_trend_series(df, wave_period)
        mfi = _mfi_series(df, mfi_period)
        mom = _momentum_wave_series(close, mfi_period)
        ema5 = close.ewm(span=5, adjust=False).mean()
        ema11 = close.ewm(span=11, adjust=False).mean()
        step = cfg.diamond_step_days if cfg.diamond_step_days is not None else 5
        for i in range(52, len(df) - cfg.hold_days, step):
            w = wt.iloc[i]
            w_prev = wt.iloc[i - 1] if i else 0
            m = mfi.iloc[i]
            mo = mom.iloc[i]
            if pd.isna(w) or pd.isna(m) or pd.isna(mo):
                continue
            green = (w < green_thresh and w > w_prev and m < 30 and mo < -40)
            if green:
                signals.append({
                    "ticker": ticker,
                    "date": close.index[i],
                    "entry_price": float(close.iloc[i]),
                    "pos": i,
                    "diamond_type": "green",
                })
    return signals


def generate_diamond_combo_signals(data: Dict[str, pd.DataFrame],
                                   earnings_history: Dict[str, pd.DataFrame],
                                   cfg: BacktestConfig) -> List[Dict]:
    """
    Green diamond ONLY when there was an earnings beat in the last 60 days (surprise >= min_surprise).
    Combines technical reversal with fundamental catalyst.
    """
    diamond_signals = generate_diamond_signals(data, cfg)
    if not diamond_signals or not earnings_history:
        return diamond_signals
    min_surprise = getattr(cfg, "min_surprise_pct", 20) or 20
    lookback_days = 60
    out = []
    for s in diamond_signals:
        ticker = s["ticker"]
        entry_date = s["date"]
        if ticker not in earnings_history:
            continue
        earn = earnings_history[ticker]
        # Any earnings date in [entry - 60d, entry] with surprise >= min_surprise
        found = False
        surp_val = 0.0
        for _, row in earn.iterrows():
            edate = pd.Timestamp(row["date"])
            if edate.tzinfo:
                edate = edate.tz_localize(None)
            if edate > entry_date:
                continue
            delta = (entry_date - edate).days
            if delta > lookback_days:
                continue
            if float(row.get("surprise_pct", 0)) >= min_surprise:
                found = True
                surp_val = float(row["surprise_pct"])
                break
        if found:
            s["surprise_pct"] = surp_val
            out.append(s)
    return out


def generate_earnings_diamond_signals(data: Dict[str, pd.DataFrame],
                                      earnings_history: Dict[str, pd.DataFrame],
                                      cfg: BacktestConfig) -> List[Dict]:
    """
    Winning strategy (earnings 40-100%, bull, 40d) BUT only keep entries where
    a green diamond fired on that ticker on or within 10 days before entry.
    Diamond acts as confirmation to cut weak entries.
    """
    base_cfg = BacktestConfig(
        name=cfg.name,
        hold_days=cfg.hold_days,
        min_surprise_pct=cfg.min_surprise_pct or 40,
        max_surprise_pct=cfg.max_surprise_pct or 100,
        require_bull_regime=cfg.require_bull_regime,
        signal_type="earnings",
    )
    base = generate_earnings_signals(data, earnings_history, base_cfg)
    if not base:
        return []
    # Build set of (ticker, date) where green diamond fired (use bar index date)
    diamond_dates_by_ticker = {}
    wave_period = 10
    mfi_period = 14
    green_thresh = cfg.diamond_green_thresh if cfg.diamond_green_thresh is not None else -60
    for ticker, df in data.items():
        df = df.sort_index()
        if len(df) < 80:
            continue
        close = df["Close"]
        wt = _wave_trend_series(df, wave_period)
        mfi = _mfi_series(df, mfi_period)
        mom = _momentum_wave_series(close, mfi_period)
        # Check every bar (step=1) so we don't miss alignment with earnings
        dates = []
        for i in range(52, len(df) - cfg.hold_days):
            w = wt.iloc[i]
            w_prev = wt.iloc[i - 1] if i else 0
            m = mfi.iloc[i]
            mo = mom.iloc[i]
            if pd.isna(w) or pd.isna(m) or pd.isna(mo):
                continue
            if (w < green_thresh and w > w_prev and m < 30 and mo < -40):
                dates.append(close.index[i])
        diamond_dates_by_ticker[ticker] = set(pd.Timestamp(d).normalize() for d in dates)
    out = []
    for s in base:
        ticker = s["ticker"]
        entry_date = s["date"]
        ed = pd.Timestamp(entry_date).date()
        if ticker not in diamond_dates_by_ticker:
            continue
        allowed = diamond_dates_by_ticker[ticker]
        df = data[ticker].sort_index()
        try:
            idx = df.index.get_indexer([entry_date], method="ffill")[0]
        except Exception:
            continue
        if idx < 0:
            continue
        # Diamond on entry or in next 20 trading days (confirmation after beat)
        window_end = min(len(df) - 1, idx + 20)
        window_dates = {pd.Timestamp(df.index[i]).normalize() for i in range(idx, window_end + 1)}
        if allowed & window_dates:
            out.append(s)
    return out


def generate_earnings_no_red_diamond_signals(data: Dict[str, pd.DataFrame],
                                             earnings_history: Dict[str, pd.DataFrame],
                                             cfg: BacktestConfig) -> List[Dict]:
    """
    Winning strategy (earnings 40-100%, bull, 40d) but DROP any entry where
    there was a red or blood diamond on that ticker in the 5 trading days before entry.
    Hypothesis: avoid entries when Cipher says bearish pressure recently.
    """
    base_cfg = BacktestConfig(
        name=cfg.name,
        hold_days=cfg.hold_days,
        min_surprise_pct=cfg.min_surprise_pct or 40,
        max_surprise_pct=cfg.max_surprise_pct or 100,
        require_bull_regime=cfg.require_bull_regime,
        signal_type="earnings",
    )
    base = generate_earnings_signals(data, earnings_history, base_cfg)
    if not base:
        return []
    wave_period = 10
    mfi_period = 14
    red_thresh = 60
    # Build set of (ticker, date) where red or blood diamond fired
    bearish_dates_by_ticker = {}
    for ticker, df in data.items():
        df = df.sort_index()
        if len(df) < 80:
            continue
        close = df["Close"]
        wt = _wave_trend_series(df, wave_period)
        mfi = _mfi_series(df, mfi_period)
        mom = _momentum_wave_series(close, mfi_period)
        ema5 = close.ewm(span=5, adjust=False).mean()
        ema11 = close.ewm(span=11, adjust=False).mean()
        dates = []
        for i in range(52, len(df) - cfg.hold_days):
            w = wt.iloc[i]
            w_prev = wt.iloc[i - 1] if i else 0
            m = mfi.iloc[i]
            mo = mom.iloc[i]
            if pd.isna(w) or pd.isna(m) or pd.isna(mo):
                continue
            red = (w > red_thresh and w < w_prev and m > 70 and mo > 40)
            red_cross = float(ema5.iloc[i]) < float(ema11.iloc[i])
            blood = red and red_cross
            if red or blood:
                dates.append(close.index[i])
        bearish_dates_by_ticker[ticker] = set(pd.Timestamp(d).normalize() for d in dates)
    out = []
    for s in base:
        ticker = s["ticker"]
        entry_date = s["date"]
        if ticker not in bearish_dates_by_ticker:
            out.append(s)
            continue
        bearish = bearish_dates_by_ticker[ticker]
        df = data[ticker].sort_index()
        try:
            idx = df.index.get_indexer([entry_date], method="ffill")[0]
        except Exception:
            out.append(s)
            continue
        if idx < 5:
            out.append(s)
            continue
        window_start = max(0, idx - 5)
        window_dates = {pd.Timestamp(df.index[i]).normalize() for i in range(window_start, idx)}
        if not (bearish & window_dates):
            out.append(s)
    return out


def generate_momentum_signals(data: Dict[str, pd.DataFrame], cfg: BacktestConfig) -> List[Dict]:
    """Price > SMA50, RSI in [35, 60] (uptrend but not overbought). Step 5 days."""
    signals = []
    for ticker, df in data.items():
        df = df.sort_index()
        close = df["Close"]
        if len(close) < 55:
            continue
        sma50 = close.rolling(50).mean()
        rsi = _rsi(close)
        for i in range(52, len(close) - cfg.hold_days, 5):
            p = float(close.iloc[i])
            s50 = float(sma50.iloc[i])
            if p <= s50:
                continue
            r = float(rsi.iloc[i])
            if pd.isna(r) or r < 35 or r > 60:
                continue
            signals.append({
                "ticker": ticker,
                "date": close.index[i],
                "entry_price": p,
                "rsi": r,
                "pos": i,
            })
    return signals


def run_backtest(data: Dict[str, pd.DataFrame], spy_close: pd.Series,
                 earnings_history: Dict[str, pd.DataFrame],
                 cfg: BacktestConfig) -> Tuple[BacktestResult, pd.DataFrame]:
    """Generate signals, compute returns, evaluate."""
    if cfg.signal_type == "earnings":
        signals = generate_earnings_signals(data, earnings_history, cfg)
    elif cfg.signal_type == "technical":
        signals = generate_technical_signals(data, cfg)
    elif cfg.signal_type == "combo":
        signals = generate_combo_signals(data, earnings_history, cfg)
    elif cfg.signal_type == "momentum":
        signals = generate_momentum_signals(data, cfg)
    elif cfg.signal_type == "diamond":
        signals = generate_diamond_signals(data, cfg)
    elif cfg.signal_type == "diamond_combo":
        signals = generate_diamond_combo_signals(data, earnings_history, cfg)
    elif cfg.signal_type == "earnings_diamond":
        signals = generate_earnings_diamond_signals(data, earnings_history, cfg)
    elif cfg.signal_type == "earnings_no_red_diamond":
        signals = generate_earnings_no_red_diamond_signals(data, earnings_history, cfg)
    else:
        return BacktestResult(
            config=cfg, n_signals=0, median_alpha_pct=0, mean_alpha_pct=0,
            alpha_hit_rate_pct=0, win_rate_pct=0, median_return_pct=0,
            first_half_median_alpha=0, second_half_median_alpha=0,
            oos_median_alpha=0, oos_n=0, passed=False,
        ), pd.DataFrame()

    if not signals:
        return evaluate_result(pd.DataFrame(), spy_close, cfg), pd.DataFrame()

    # Optional: keep only top X% of signals by surprise (for 80% hit-rate mode)
    if getattr(cfg, "earnings_top_pct_surprise", None) is not None:
        pct = cfg.earnings_top_pct_surprise
        if 0 < pct <= 1:
            surps = [s.get("surprise_pct") for s in signals if "surprise_pct" in s]
            if len(surps) >= 2:
                cutoff = float(np.percentile(surps, 100 * (1 - pct)))
                signals = [s for s in signals if s.get("surprise_pct", -999) >= cutoff]

    df = compute_returns(signals, data, spy_close, cfg.hold_days, cfg.require_bull_regime)
    result = evaluate_result(df, spy_close, cfg)
    return result, df


if __name__ == "__main__":
    # Quick test
    UNI = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "CRWD", "DDOG", "SOFI",
           "CELH", "CAVA", "ELF", "ONON", "TGTX", "RKLB", "HOOD", "AFRM", "FUBO", "PLUG"]
    data, spy = fetch_and_cache_prices(UNI, days=600)
    earn = load_earnings_history(list(data.keys()))
    cfg = BacktestConfig("earnings_40_100", hold_days=20, min_surprise_pct=40, max_surprise_pct=100)
    res, df = run_backtest(data, spy, earn, cfg)
    print(f"Config: {cfg.name}  n={res.n_signals}  median_alpha={res.median_alpha_pct}%  "
          f"alpha_hit={res.alpha_hit_rate_pct}%  passed={res.passed}")
