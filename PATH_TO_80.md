# Path to 80% Alpha Hit Rate

## Target

You asked to **aim for at least 80%** (alpha hit rate: fraction of signals that beat SPY).

## What We Did

1. **Stacked every filter we have**
   - Earnings band: 40–100%, 50–100%, 60–100%, 70–100%, 80–100%
   - Bull regime only (SPY > 200d MA)
   - **No red/blood diamond** in 5 days before entry (exclude bearish Cipher pressure)
   - **Top % by surprise**: keep only top 50%, 33%, 25%, or 10% of signals by surprise
   - Hold 20 or 30 days

2. **Searched the full universe** (102 tickers from strategy_search) with 100 configs.

3. **Relaxed min_signals** to 10 for “80% mode” so we could report high–hit-rate configs even with fewer signals.

## Result: Ceiling ~67%

- **No config reached 80%** alpha hit with n ≥ 10.
- **Best observed:** **66.7%** alpha hit, **n = 6**, median alpha **+7.75%**  
  - Config: earnings 40–100% (or 50–100%, 60–100%, 70–100% — same 6 signals), **top 10% by surprise**, hold **20d**, bull, with or without no_red_diamond.
- With n ≥ 10, best was **64.3%** (50–100% surprise, top 33%, hold 20d, n=14).
- With n ≥ 15, no config reached 70%.

So with **free data and this universe**, we are **capped around 66–67%** alpha hit when we want at least 10 signals. Pushing to 80% would require either:
- **n &lt; 5** (not a robust system), or  
- **Different data** (e.g. paid alternative data, or a different segment/regime we haven’t tested), or  
- **Overfitting** (would fail out-of-sample).

## Best “Toward 80%” Config (Use This for Aggressive Mode)

| Parameter        | Value |
|------------------|--------|
| Surprise band    | 40–100% |
| Top % by surprise| **Top 25%** (or top 10% for fewer signals) |
| Hold days        | **20** |
| Bull regime only | Yes |
| No red diamond   | Optional (same 6 signals with/without) |

Backtest: **n = 6**, **66.7%** alpha hit, **+7.75%** median alpha when using **top 10%**; **n = 15**, **60%** alpha hit, **+1.27%** median alpha when using **top 25%** with no_red_diamond.

For **live “aggressive” mode**: use same rules as winning strategy but **hold 20d** and **keep only the top 25% of current signals by surprise**. That yields fewer, higher-conviction signals and should sit in the **low-to-mid 60s** hit rate in line with backtest.

## How to Run

- **Full 80% search:**  
  `python3 search_80.py`  
  Prints best configs by alpha hit; saves best to `backtest_cache/strategy_80_mode.json` if any reach ≥70% with n≥10.

- **Aggressive live signals (fewer, higher conviction):**  
  `python3 run_winning_strategy.py --mode aggressive`  
  Uses hold 20d and keeps only top 25% of signals by surprise (see run_winning_strategy.py).

## Bottom Line

- **80% with n ≥ 10 is not achieved** in backtest; ceiling is **~67%** with maximum selectivity.
- **Aggressive mode** (top 25% by surprise, hold 20d) is the best “toward 80%” trade-off we have; use it when you want fewer, higher-conviction signals and accept ~60–67% hit rate.
