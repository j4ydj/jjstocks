# Backtest: before vs after adaptive filters

> Generated: **2026-05-18**  
> Compares unfiltered rules vs filters learned from poor performance.

## What changed (adaptive rules)

| Filter | Reason |
|--------|--------|
| **Leader moved yesterday**, focus lags today | Same-day cluster moves lost money; avoids chasing |
| **No divergence** | ~33% win, negative avg in backtest |
| **No BUY catch-up** | ~33% win vs ~39% for SHORT |
| **13 blocked pairs** | e.g. COIN/RIOT, JOBY/ARKK (win ≤32%, avg negative, n≥15) |

Live system uses `data/setup_scores.json` from `python setup_learning.py --rebuild`.

## 2-year P&L comparison

| Metric | Before (`BACKTEST_SETUPS_2Y.csv`) | After (`BACKTEST_SETUPS_ADAPTIVE.csv`) |
|--------|-----------------------------------|----------------------------------------|
| Trades | 2,149 | 709 |
| Win rate | 36.7% | 35.1% |
| Avg return / trade | +0.05% | **+0.09%** |
| Median return | -3.03% | -3.21% |
| Stopped out | ~56% | ~56% |

**Read honestly:** Adaptive filters cut **67%** of trades and slightly **improved average return** but did **not** fix win rate (~35%). Median trade is still negative.

## 1-year (reference)

| Metric | Before | After adaptive |
|--------|--------|----------------|
| Trades | 676 | ~250 (run `backtest_setups.py --years 1 --adaptive`) |
| Win rate | 35.8% | ~35% |

## Why win rate stays ~35%

1. **Stops still hit ~57%** — volatile names, 2×ATR stops.
2. **Hit rate ≠ trade win** — correlation tests same-day direction; we enter next open.
3. **Edge is thin** — breakeven average with negative median = a few big wins, many small losses.

## What to track live

Forward validation only counts under **new** rules:

```bash
python trade_tracker.py --fill
python trade_tracker.py --report
```

Compare `trade_setups.jsonl` (live) against this file after 30+ trades.

## Reproduce

```bash
# Unfiltered (slow)
python backtest_setups.py --years 2 --out BACKTEST_SETUPS_2Y.md --csv data/BACKTEST_SETUPS_2Y.csv

# Adaptive (what we ship now)
python backtest_setups.py --years 2 --adaptive --out BACKTEST_SETUPS_ADAPTIVE.md --csv data/BACKTEST_SETUPS_ADAPTIVE.csv

python setup_learning.py --rebuild
```
