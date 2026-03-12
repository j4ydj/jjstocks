#!/usr/bin/env python3
"""
Unified data fetcher with fallbacks to avoid rate limits and API errors.

- Primary: yfinance (free, no key).
- Optional paid/preferred: Polygon.io (POLYGON_API_KEY), Tiingo (TIINGO_API_KEY).
- Fallback: Alpha Vantage (ALPHA_VANTAGE_API_KEY, free tier).
- Retries with backoff on failure.

See PAID_DATA_AND_PATH.md for paid sources and integration plan.
"""

import os
import time
import logging
from typing import Optional, Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def _polygon_history(ticker: str, days: int, api_key: str) -> Optional[pd.DataFrame]:
    """Fetch daily aggregates from Polygon.io. Requires paid plan (e.g. Starter $29/mo)."""
    try:
        import requests
        # Polygon aggregates: /v2/aggs/ticker/{ticker}/range/1/day/from/to
        to_ts = pd.Timestamp.now()
        from_ts = to_ts - pd.Timedelta(days=days)
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/"
            f"{from_ts.strftime('%Y-%m-%d')}/{to_ts.strftime('%Y-%m-%d')}"
            f"?apiKey={api_key}&adjusted=true&sort=asc&limit=50000"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        j = r.json()
        if j.get("resultsCount", 0) == 0:
            return None
        rows = []
        for bar in j.get("results", []):
            t = bar.get("t", 0)
            row = {
                "Open": bar.get("o"),
                "High": bar.get("h"),
                "Low": bar.get("l"),
                "Close": bar.get("c"),
                "Volume": bar.get("v", 0),
            }
            if t:
                row["Date"] = pd.Timestamp(t, unit="ms")
            else:
                continue
            rows.append(row)
        if not rows:
            return None
        df = pd.DataFrame(rows)
        if "Date" not in df.columns:
            return None
        df = df.set_index("Date").sort_index()
        if len(df) < 60:
            return None
        return df
    except Exception as e:
        logger.debug("Polygon %s: %s", ticker, e)
        return None


def _tiingo_history(ticker: str, days: int, api_key: str) -> Optional[pd.DataFrame]:
    """Fetch EOD from Tiingo. Power plan ~$30/mo for high limits."""
    try:
        import requests
        url = (
            f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?"
            f"startDate={pd.Timestamp.now() - pd.Timedelta(days=days):%Y-%m-%d}&token={api_key}"
        )
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        df = pd.DataFrame(data)
        if "date" not in df.columns or "close" not in df.columns:
            return None
        df = df.rename(columns={"date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        if len(df) < 60:
            return None
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception as e:
        logger.debug("Tiingo %s: %s", ticker, e)
        return None


def _yfinance_history(ticker: str, days: int = 756):
    """Fetch OHLCV via yfinance. Returns None on failure."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        df = t.history(period=f"{days}d", interval="1d", auto_adjust=True)
        if df is None or df.empty or len(df) < 60:
            return None
        df.index = pd.to_datetime(df.index)
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        logger.debug("yfinance %s: %s", ticker, e)
        return None


def _alpha_vantage_history(ticker: str, days: int, api_key: str) -> Optional[pd.DataFrame]:
    """Fetch daily OHLC from Alpha Vantage. Free tier: 25 req/day."""
    try:
        import requests
        url = (
            "https://www.alphavantage.co/query"
            "?function=TIME_SERIES_DAILY_ADJUSTED"
            "&symbol={}&apikey={}&outputsize=full"
        ).format(ticker, api_key)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        j = r.json()
        ts = j.get("Time Series (Daily)")
        if not ts:
            return None
        rows = []
        for d, v in ts.items():
            rows.append({
                "Date": d,
                "Open": float(v.get("1. open", 0)),
                "High": float(v.get("2. high", 0)),
                "Low": float(v.get("3. low", 0)),
                "Close": float(v.get("5. adjusted close", v.get("4. close", 0))),
                "Volume": int(float(v.get("6. volume", 0))),
            })
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        if len(df) < 60:
            return None
        # Limit to requested window
        if len(df) > days + 50:
            df = df.iloc[-(days + 50):]
        return df
    except Exception as e:
        logger.debug("Alpha Vantage %s: %s", ticker, e)
        return None


def get_stock_history(
    ticker: str,
    days: int = 756,
    api_key: Optional[str] = None,
    use_fallback: bool = True,
    prefer_paid: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Get OHLCV DataFrame for one ticker.
    Order when prefer_paid=True: Polygon (if POLYGON_API_KEY) -> Tiingo (if TIINGO_API_KEY) -> yfinance -> Alpha Vantage.
    When prefer_paid=False or no paid keys: yfinance -> Alpha Vantage.
    """
    days = min(days, 756)
    key_av = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")
    key_polygon = os.environ.get("POLYGON_API_KEY")
    key_tiingo = os.environ.get("TIINGO_API_KEY")

    if prefer_paid and key_polygon:
        df = _polygon_history(ticker, days, key_polygon)
        if df is not None:
            return df
    if prefer_paid and key_tiingo:
        df = _tiingo_history(ticker, days, key_tiingo)
        if df is not None:
            return df

    df = _yfinance_history(ticker, days)
    if df is not None:
        return df
    if use_fallback and key_av:
        df = _alpha_vantage_history(ticker, days, key_av)
        if df is not None:
            logger.info("Used Alpha Vantage fallback for %s", ticker)
            return df
    return None


def fetch_prices_bulk(
    tickers: List[str],
    days: int = 756,
    batch_size: int = 20,
    delay: float = 0.5,
    retries: int = 2,
    fallback_per_ticker: bool = True,
    api_key: Optional[str] = None,
) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """
    Fetch OHLCV for many tickers. Returns (data dict, list of tickers that failed).
    Uses yfinance in batches with delay; optionally fills missing tickers via fallback.
    """
    import yfinance as yf
    tickers = list(dict.fromkeys(t.upper() for t in tickers))
    data = {}
    failed = []
    key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")

    for attempt in range(retries + 1):
        for i in range(0, len(tickers), batch_size):
            batch = [t for t in tickers[i : i + batch_size] if t not in data]
            if not batch:
                continue
            joined = " ".join(batch)
            try:
                raw = yf.download(
                    joined,
                    period=f"{days}d",
                    interval="1d",
                    group_by="ticker",
                    threads=True,
                    progress=False,
                    auto_adjust=True,
                )
                if raw is None or raw.empty:
                    if len(batch) == 1:
                        failed.append(batch[0])
                    else:
                        failed.extend(batch)
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
                        failed.append(tk)
                else:
                    try:
                        ticker_level = raw.columns.get_level_values(0).unique().tolist() if hasattr(raw.columns, "get_level_values") else []
                    except Exception:
                        ticker_level = []
                    for tk in batch:
                        try:
                            if tk in ticker_level:
                                df = raw[tk].copy()
                                if hasattr(df, "columns"):
                                    df.columns = [c for c in df.columns]
                                df = df.dropna(how="all")
                                df.index = pd.to_datetime(df.index)
                                if hasattr(df.index, "tz") and df.index.tz is not None:
                                    df.index = df.index.tz_localize(None)
                                if len(df) >= 60 and "Close" in df.columns:
                                    data[tk] = df
                            else:
                                failed.append(tk)
                        except Exception:
                            failed.append(tk)
            except Exception as e:
                logger.warning("Batch download error: %s", e)
                for t in batch:
                    if t not in data:
                        failed.append(t)
            time.sleep(delay)

        still_missing = [t for t in tickers if t not in data]
        if not still_missing or not fallback_per_ticker or not key:
            failed = still_missing
            break
        # Per-ticker fallback for missing
        for t in still_missing:
            df = _alpha_vantage_history(t, days, key)
            if df is not None:
                data[t] = df
                logger.info("Fallback: %s via Alpha Vantage", t)
            else:
                failed.append(t)
            time.sleep(0.3)
        failed = [t for t in tickers if t not in data]
        if not failed:
            break
        if attempt < retries:
            time.sleep(2.0 * (attempt + 1))

    return data, failed
