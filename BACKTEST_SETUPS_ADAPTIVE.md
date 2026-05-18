# Setup P&L backtest (actionable rules)

> Generated: **2026-05-18 12:18:32**
> Period: **2y** | Hold: **5d** max | Corr window: **60d** | Min |r|: **0.55** | Min hit: **55.0%**
> Focus tickers: 15 | Simulated trades: **709**

## Already available (relationship validation only)

- `BACKTEST_LEAD_LAG.md` + `data/BACKTEST_LEAD_LAG.csv` — correlation & directional hit rates (not P&L)
- This file — **simulated P&L** using catch_up / divergence rules + stops/targets

## Overall

| Metric | Value |
|--------|-------|
| Trades | 709 |
| Win rate | 35.1% |
| Avg return / trade | +0.09% |
| Median return | -3.21% |
| Sum of returns (not compounded) | +62.37% |
| Stopped out | 57.8% |
| Hit target | 22.8% |

## By setup type

### catch_up
- Trades: **709** | Win: **35.1%** | Avg: **+0.09%** | Median: **-3.21%**

### divergence
_No trades._

## By focus ticker

| Focus | Trades | Win% | Avg% |
|-------|--------|------|------|
| AMD | 74 | 23.0% | -1.51% |
| ASTS | 13 | 38.5% | +1.17% |
| COIN | 83 | 42.2% | +1.28% |
| DDOG | 20 | 15.0% | -2.56% |
| GME | 23 | 34.8% | -0.11% |
| HOOD | 54 | 46.3% | +1.28% |
| IONQ | 15 | 33.3% | -0.56% |
| JOBY | 21 | 33.3% | +0.28% |
| LUNR | 16 | 37.5% | +1.03% |
| MSTR | 118 | 43.2% | +1.32% |
| NVDA | 96 | 35.4% | -0.32% |
| PLTR | 45 | 40.0% | +0.12% |
| RKLB | 61 | 19.7% | -1.72% |
| SMCI | 31 | 29.0% | -0.75% |
| SOFI | 39 | 35.9% | +0.52% |

## Last 40 trades (most recent)

| Date | Type | Dir | Focus | Leader | Corr | Ret% | Stop | Tgt |
|------|------|-----|-------|--------|------|------|------|-----|
| 2026-03-30 | catch_up | SHORT | COIN | BTC-USD | +0.81 | -4.68% | True | False |
| 2026-03-30 | catch_up | SHORT | MSTR | COIN | +0.82 | -4.70% | True | False |
| 2026-03-30 | catch_up | SHORT | HOOD | ARKK | +0.85 | -4.72% | True | False |
| 2026-03-31 | catch_up | SHORT | MSTR | RIOT | +0.70 | -4.71% | True | False |
| 2026-04-06 | catch_up | SHORT | NVDA | ASML | +0.67 | -2.00% | True | False |
| 2026-04-08 | catch_up | SHORT | NVDA | ^VIX | -0.63 | -1.72% | True | False |
| 2026-04-10 | catch_up | SHORT | RKLB | ASTS | +0.78 | -4.83% | True | False |
| 2026-04-10 | catch_up | SHORT | COIN | HOOD | +0.85 | -4.84% | True | False |
| 2026-04-10 | catch_up | SHORT | MSTR | COIN | +0.81 | -4.42% | True | False |
| 2026-04-15 | catch_up | SHORT | RKLB | ASTS | +0.75 | -1.47% | True | False |
| 2026-04-16 | catch_up | SHORT | NVDA | ASML | +0.66 | -1.02% | True | False |
| 2026-04-17 | catch_up | SHORT | NVDA | ASML | +0.66 | -4.80% | True | False |
| 2026-04-17 | catch_up | SHORT | AMD | TSM | +0.60 | -4.73% | True | False |
| 2026-04-21 | catch_up | SHORT | RKLB | ASTS | +0.74 | +13.30% | False | True |
| 2026-04-21 | catch_up | SHORT | NVDA | ^VIX | -0.59 | -1.41% | True | False |
| 2026-04-21 | catch_up | SHORT | HOOD | ^VIX | -0.57 | +18.23% | False | True |
| 2026-04-22 | catch_up | SHORT | NVDA | ARKK | +0.68 | -4.76% | True | False |
| 2026-04-22 | catch_up | SHORT | HOOD | ^VIX | -0.58 | +12.72% | False | True |
| 2026-04-24 | catch_up | SHORT | RKLB | ASTS | +0.74 | -4.76% | True | False |
| 2026-04-24 | catch_up | SHORT | PLTR | ARKK | +0.69 | -3.27% | False | False |
| 2026-04-24 | catch_up | SHORT | COIN | HOOD | +0.86 | +11.15% | False | True |
| 2026-04-24 | catch_up | SHORT | MSTR | COIN | +0.81 | -6.68% | True | False |
| 2026-04-24 | catch_up | SHORT | IONQ | ARKK | +0.75 | -4.81% | True | False |
| 2026-04-24 | catch_up | SHORT | HOOD | ARKK | +0.88 | +11.17% | False | True |
| 2026-04-27 | catch_up | SHORT | RKLB | SPCE | +0.59 | +1.67% | False | False |
| 2026-04-28 | catch_up | SHORT | NVDA | AMD | +0.57 | +3.56% | False | True |
| 2026-04-28 | catch_up | SHORT | MSTR | MARA | +0.77 | -4.76% | True | False |
| 2026-04-29 | catch_up | SHORT | RKLB | ASTS | +0.74 | -4.73% | True | False |
| 2026-04-29 | catch_up | SHORT | NVDA | AMD | +0.58 | +7.78% | False | True |
| 2026-04-29 | catch_up | SHORT | MSTR | RIOT | +0.77 | -4.66% | True | False |
| 2026-04-30 | catch_up | SHORT | PLTR | ARKK | +0.72 | +3.96% | False | False |
| 2026-04-30 | catch_up | SHORT | COIN | HOOD | +0.86 | -4.67% | True | False |
| 2026-04-30 | catch_up | SHORT | MSTR | COIN | +0.82 | -4.62% | True | False |
| 2026-04-30 | catch_up | SHORT | HOOD | ^VIX | -0.60 | -4.70% | True | False |
| 2026-05-01 | catch_up | SHORT | NVDA | META | +0.63 | -6.03% | True | False |
| 2026-05-04 | catch_up | SHORT | RKLB | ASTS | +0.70 | -4.64% | True | False |
| 2026-05-05 | catch_up | SHORT | RKLB | ASTS | +0.69 | -4.72% | True | False |
| 2026-05-05 | catch_up | SHORT | JOBY | ^VIX | -0.57 | -4.62% | True | False |
| 2026-05-05 | catch_up | SHORT | HOOD | ^VIX | -0.56 | +1.37% | False | False |
| 2026-05-06 | catch_up | SHORT | MSTR | COIN | +0.79 | +4.05% | False | True |

## CSV

`data/BACKTEST_SETUPS_ADAPTIVE.csv`

## Reproduce

```bash
python backtest_setups.py --years 2
```
