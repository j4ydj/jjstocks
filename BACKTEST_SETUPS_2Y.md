# Setup P&L backtest (actionable rules)

> Generated: **2026-05-18 11:48:58**
> Period: **2y** | Hold: **5d** max | Corr window: **60d** | Min |r|: **0.55** | Min hit: **55.0%**
> Focus tickers: 15 | Simulated trades: **2149**

## Already available (relationship validation only)

- `BACKTEST_LEAD_LAG.md` + `data/BACKTEST_LEAD_LAG.csv` — correlation & directional hit rates (not P&L)
- This file — **simulated P&L** using catch_up / divergence rules + stops/targets

## Overall

| Metric | Value |
|--------|-------|
| Trades | 2149 |
| Win rate | 36.7% |
| Avg return / trade | +0.05% |
| Median return | -3.03% |
| Sum of returns (not compounded) | +108.93% |
| Stopped out | 56.2% |
| Hit target | 21.9% |

## By setup type

### catch_up
- Trades: **1814** | Win: **37.4%** | Avg: **+0.10%** | Median: **-3.10%**

### divergence
- Trades: **335** | Win: **32.8%** | Avg: **-0.23%** | Median: **-2.74%**

## By focus ticker

| Focus | Trades | Win% | Avg% |
|-------|--------|------|------|
| AMD | 195 | 39.5% | +0.47% |
| ASTS | 29 | 27.6% | -1.17% |
| COIN | 386 | 29.5% | -0.58% |
| DDOG | 56 | 53.6% | +1.19% |
| GME | 43 | 37.2% | +0.07% |
| HOOD | 104 | 42.3% | +1.01% |
| IONQ | 37 | 37.8% | +1.09% |
| JOBY | 58 | 29.3% | -1.46% |
| LUNR | 39 | 51.3% | +2.87% |
| MSTR | 301 | 38.2% | +0.31% |
| NVDA | 299 | 41.1% | +0.00% |
| PLTR | 100 | 45.0% | +0.62% |
| RKLB | 271 | 29.2% | -0.48% |
| SMCI | 105 | 37.1% | -0.43% |
| SOFI | 126 | 38.1% | +0.43% |

## Last 40 trades (most recent)

| Date | Type | Dir | Focus | Leader | Corr | Ret% | Stop | Tgt |
|------|------|-----|-------|--------|------|------|------|-----|
| 2026-04-29 | catch_up | SHORT | MSTR | COIN | +0.82 | -4.66% | True | False |
| 2026-04-29 | catch_up | SHORT | JOBY | ^VIX | -0.56 | -4.66% | True | False |
| 2026-04-30 | catch_up | BUY | RKLB | PL | +0.60 | -4.94% | True | False |
| 2026-04-30 | catch_up | BUY | PLTR | ARKK | +0.72 | -3.09% | True | False |
| 2026-04-30 | catch_up | SHORT | PLTR | SNOW | +0.58 | +3.96% | False | False |
| 2026-04-30 | divergence | BUY | NVDA | ASML | +0.60 | -1.17% | True | False |
| 2026-04-30 | catch_up | SHORT | NVDA | META | +0.64 | -5.86% | True | False |
| 2026-04-30 | catch_up | BUY | COIN | MARA | +0.69 | +4.84% | False | False |
| 2026-04-30 | catch_up | BUY | MSTR | MARA | +0.76 | +9.83% | False | False |
| 2026-04-30 | catch_up | BUY | JOBY | ^VIX | -0.60 | -5.05% | True | False |
| 2026-04-30 | catch_up | BUY | HOOD | ^VIX | -0.60 | +4.41% | False | False |
| 2026-05-01 | divergence | BUY | RKLB | LUNR | +0.76 | +12.30% | False | True |
| 2026-05-01 | catch_up | BUY | AMD | INTC | +0.75 | -5.00% | True | False |
| 2026-05-01 | catch_up | SHORT | COIN | MARA | +0.68 | -4.57% | True | False |
| 2026-05-01 | divergence | SHORT | COIN | MARA | +0.68 | -4.57% | True | False |
| 2026-05-01 | catch_up | BUY | COIN | MSTR | +0.82 | -6.84% | True | False |
| 2026-05-01 | divergence | SHORT | MSTR | MARA | +0.74 | -3.25% | True | False |
| 2026-05-04 | catch_up | SHORT | RKLB | ASTS | +0.70 | -4.64% | True | False |
| 2026-05-04 | divergence | SHORT | RKLB | ASTS | +0.70 | -4.64% | True | False |
| 2026-05-04 | catch_up | SHORT | NVDA | ASML | +0.58 | -6.03% | True | False |
| 2026-05-04 | catch_up | SHORT | JOBY | ^VIX | -0.57 | -7.23% | True | False |
| 2026-05-04 | catch_up | SHORT | HOOD | ^VIX | -0.56 | -0.84% | False | False |
| 2026-05-05 | catch_up | SHORT | RKLB | ASTS | +0.69 | -4.72% | True | False |
| 2026-05-05 | catch_up | BUY | SMCI | XLK | +0.57 | +8.84% | False | True |
| 2026-05-05 | catch_up | BUY | NVDA | SMH | +0.69 | +9.83% | False | True |
| 2026-05-05 | catch_up | BUY | AMD | INTC | +0.75 | +8.68% | False | True |
| 2026-05-05 | divergence | SHORT | AMD | TSM | +0.59 | -1.81% | True | False |
| 2026-05-05 | divergence | BUY | COIN | BTC-USD | +0.69 | -5.05% | True | False |
| 2026-05-05 | divergence | SHORT | MSTR | COIN | +0.79 | -1.87% | True | False |
| 2026-05-05 | catch_up | BUY | MSTR | MARA | +0.56 | -3.54% | False | False |
| 2026-05-05 | catch_up | BUY | JOBY | ^VIX | -0.57 | +11.05% | False | True |
| 2026-05-05 | catch_up | SHORT | HOOD | ARKK | +0.86 | +1.37% | False | False |
| 2026-05-05 | catch_up | BUY | HOOD | XLK | +0.62 | -1.35% | False | False |
| 2026-05-06 | catch_up | BUY | RKLB | ASTS | +0.70 | -4.99% | True | False |
| 2026-05-06 | catch_up | BUY | PLTR | ARKK | +0.63 | +3.91% | False | True |
| 2026-05-06 | catch_up | BUY | NVDA | ASML | +0.58 | +12.57% | False | True |
| 2026-05-06 | catch_up | BUY | COIN | ARKK | +0.76 | -5.05% | True | False |
| 2026-05-06 | catch_up | BUY | MSTR | ARKK | +0.69 | -5.06% | True | False |
| 2026-05-06 | catch_up | BUY | HOOD | ARKK | +0.85 | -5.00% | True | False |
| 2026-05-06 | catch_up | BUY | SOFI | ARKK | +0.70 | -4.92% | True | False |

## CSV

`data/BACKTEST_SETUPS_2Y.csv`

## Reproduce

```bash
python backtest_setups.py --years 2
```
