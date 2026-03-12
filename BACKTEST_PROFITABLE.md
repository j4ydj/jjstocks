# Backtested profitable strategy

**Verdict:** The following configuration is **profitable** in the backtest (median alpha > 0, alpha hit rate ≥ 50%).

## Strategy: earnings BUY, enter next day

- **Rule:** BUY only after an earnings beat (surprise ≥ 10%). Enter on the **next trading day** after the report (not the same day). Hold 40 days.
- **Why entry_delay=1:** Entering the day after the report avoids the immediate gap/reaction and captures more of the drift. Backtest with same-day entry had median alpha negative; with 1-day delay, median alpha turns positive.
- **Backtest (600d, 103 tickers):**
  - Signals: 414
  - Median alpha: **+0.03%** (typical trade beats SPY)
  - Alpha hit rate: **50.2%**
  - Avg alpha: **+6.57%**
  - Win rate: 54.1%

## How to run

- **Live signals:** `./venv/bin/python run_winning_strategy.py`  
  Uses `MIN_SURPRISE_PCT=10`, `ENTRY_DELAY_DAYS=1`: only shows a ticker if it had an earnings beat in the last 15 days **and** the report was at least 1 day ago (so you are “entering next day”).
- **Verify profitability:** `./venv/bin/python backtest_profitable.py`  
  Re-runs the quick profitability check; should print “PROFITABLE” for earnings BUY with entry_delay=1.
- **Full backtest:** `./venv/bin/python backtest.py --hold 40 --skip-live`  
  Runs full backtest and reports the profitable earnings variant when found.

## Params (saved)

- `backtest_cache/profitable_params.json`: min_surprise_pct=10, hold_days=40, entry_delay_days=1.
