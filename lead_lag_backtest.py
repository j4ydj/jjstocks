#!/usr/bin/env python3
"""
Report forward hit rates for lead/lag links (validates predictions, not just correlation).

  python lead_lag_backtest.py
  python lead_lag_backtest.py --tickers RKLB,DDOG,SMCI --days 120
"""
from __future__ import annotations

import argparse
import os

import yfinance as yf

from chain_stats import lead_lag_hit_rate
from momentum_chain import CORR_LOOKBACK_DAYS, daily_returns, lead_lag_corr


def _close_series(ticker: str, period: str):
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return None
    s = df["Close"]
    return s.squeeze() if hasattr(s, "squeeze") else s


def report_pair(focus: str, node: str, period: str = "6mo") -> None:
    f_close = _close_series(focus, period)
    n_close = _close_series(node, period)
    if f_close is None or n_close is None:
        print(f"  {focus}/{node}: no data")
        return
    fr = daily_returns(f_close).tail(CORR_LOOKBACK_DAYS + 40)
    nr = daily_returns(n_close).reindex(fr.index).dropna()
    fr = fr.reindex(nr.index).dropna()
    corr, lag = lead_lag_corr(fr, nr)
    hit, n = lead_lag_hit_rate(fr, nr, lag, corr, min_events=5)
    lag_s = f"leads {focus} ~{lag}d" if lag > 0 else (f"lags {focus} ~{-lag}d" if lag < 0 else "same day")
    hit_s = f"{hit:.1f}% over {n} events" if hit is not None else f"insufficient events (n={n})"
    print(f"  {node} → {focus}: corr={corr:+.2f} {lag_s} | forward hit: {hit_s}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", default="RKLB,DDOG,SMCI,AKAM,JOBY")
    p.add_argument("--macro", default="SMH,ARKK,^VIX,USO")
    p.add_argument("--period", default="6mo")
    args = p.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    macros = [m.strip() for m in args.macro.split(",") if m.strip()]

    print(f"Lead/lag forward validation (lookback={CORR_LOOKBACK_DAYS}d, period={args.period})\n")
    for focus in tickers:
        print(f"{focus}:")
        for node in macros:
            report_pair(focus, node, args.period)
        print()


if __name__ == "__main__":
    main()
