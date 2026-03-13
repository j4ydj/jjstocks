#!/usr/bin/env python3
"""
Backtest for Edge-style strategy (Backtrader).
Runs on a single stock + SPY for a quick sanity check.
"""
import datetime
import sys

import backtrader as bt
import pandas as pd
import yfinance as yf


class EdgeStrategy(bt.Strategy):
    params = (
        ("atr_period", 14),
        ("hold_days", 30),
        ("risk_pct", 0.02),  # 2% portfolio risk
    )

    def __init__(self):
        self.stock = self.datas[0]
        self.spy = self.datas[1]

        self.sma20 = bt.indicators.SMA(self.stock.close, period=20)
        self.sma50 = bt.indicators.SMA(self.stock.close, period=50)
        self.stock_roc = bt.indicators.ROC(self.stock.close, period=63)
        self.spy_roc = bt.indicators.ROC(self.spy.close, period=63)
        self.vol_sma = bt.indicators.SMA(self.stock.volume, period=20)
        self.atr = bt.indicators.ATR(self.stock, period=self.params.atr_period)

        self.order = None
        self.entry_bar = None
        self.stop_price = None
        self.target_price = None

    def next(self):
        if self.order:
            return

        # --- EXIT ---
        if self.position:
            days_in_trade = len(self) - self.entry_bar
            if days_in_trade >= self.params.hold_days:
                self.close()
                return
            if self.stock.close[0] <= self.stop_price:
                self.close()
                return
            if self.stock.close[0] >= self.target_price:
                self.close()
                return
            return

        # --- ENTRY (3 signals, need >= 2) ---
        conviction = 0
        if (
            self.stock.close[0] > self.sma20[0]
            and self.stock.close[0] > self.sma50[0]
            and self.sma20[0] > self.sma50[0]
        ):
            conviction += 1
        if (self.stock_roc[0] - self.spy_roc[0]) > 0.05:
            conviction += 1
        if self.stock.volume[0] > (1.5 * self.vol_sma[-1]) and self.stock.close[0] > self.stock.close[-1]:
            conviction += 1

        if conviction >= 2:
            entry = float(self.stock.close[0])
            stop = entry - (2.0 * self.atr[0])
            risk_per_share = entry - stop
            if risk_per_share <= 0:
                return
            target = entry + (2.0 * risk_per_share)
            self.stop_price = stop
            self.target_price = target

            risk_amount = self.broker.getcash() * self.params.risk_pct
            size = int(risk_amount / risk_per_share)
            if size > 0:
                self.buy(size=size)
                self.entry_bar = len(self)
                self._trades_done = getattr(self, "_trades_done", 0) + 1


def _prepare_df(ticker: str, start: str, end: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if raw.empty or len(raw) < 63:
        return raw
    # Normalize: yfinance can return MultiIndex columns for single ticker in some versions
    if isinstance(raw.columns, pd.MultiIndex):
        raw = raw.copy()
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
    col_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    out = pd.DataFrame(index=pd.to_datetime(raw.index))
    for old, new in col_map.items():
        if old in raw.columns:
            out[new] = raw[old].values
    if len(out.columns) != 5:
        return pd.DataFrame()
    return out.dropna()


def run_backtest(
    stock_ticker: str = "AAPL",
    start: str = "2020-01-01",
    end: str = "2024-01-01",
    cash: float = 100_000.0,
):
    cerebro = bt.Cerebro()
    stock_df = _prepare_df(stock_ticker, start, end)
    spy_df = _prepare_df("SPY", start, end)
    if stock_df.empty or spy_df.empty or len(stock_df) < 63:
        print("Not enough data")
        return None

    data0 = bt.feeds.PandasData(dataname=stock_df)
    data1 = bt.feeds.PandasData(dataname=spy_df)
    cerebro.adddata(data0, name=stock_ticker)
    cerebro.adddata(data1, name="SPY")
    cerebro.addstrategy(EdgeStrategy)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=0.001)
    start_val = cerebro.broker.getvalue()
    cerebro.addobserver(bt.observers.Broker)
    run_result = cerebro.run()
    end_val = cerebro.broker.getvalue()
    strat = run_result[0][0] if run_result else None
    n_trades = getattr(strat, "_trades_done", 0) if strat else 0
    return {
        "ticker": stock_ticker,
        "start_val": start_val,
        "end_val": end_val,
        "return_pct": (end_val - start_val) / start_val * 100,
        "n_trades": n_trades,
    }


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2024-01-01"
    print("Downloading data...")
    result = run_backtest("AAPL", start=start, end=end)
    if result:
        print(f"  Ticker:     {result['ticker']}")
        print(f"  Start:      ${result['start_val']:,.2f}")
        print(f"  End:        ${result['end_val']:,.2f}")
        print(f"  Return:     {result['return_pct']:.2f}%")
        print(f"  # entries:  {result.get('n_trades', 'N/A')}")
        # Buy-and-hold SPY for comparison
        spy = _prepare_df("SPY", start, end)
        if not spy.empty and "close" in spy.columns:
            spy_ret = (spy["close"].iloc[-1] / spy["close"].iloc[0] - 1) * 100
            print(f"  SPY B&H:    {spy_ret:.2f}% (same period)")
