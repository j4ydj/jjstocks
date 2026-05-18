# Setup P&L backtest (actionable rules)

> Generated: **2026-05-18 11:46:56**
> Period: **1y** | Hold: **5d** max | Corr window: **60d** | Min |r|: **0.55** | Min hit: **55.0%**
> Focus tickers: 15 | Simulated trades: **676**

## Related reports

| File | What it tests |
|------|----------------|
| `BACKTEST_LEAD_LAG.md` + `data/BACKTEST_LEAD_LAG.csv` | Correlation & **directional** hit rate (not P&L) |
| **`BACKTEST_SETUPS.md`** (this file) | **P&L** — 1 year, catch_up + divergence + stops |
| `BACKTEST_SETUPS_2Y.md` + `data/BACKTEST_SETUPS_2Y.csv` | Same rules over **2 years** |

## Overall

| Metric | Value |
|--------|-------|
| Trades | 676 |
| Win rate | 35.8% |
| Avg return / trade | -0.01% |
| Median return | -3.20% |
| Sum of returns (not compounded) | -4.17% |
| Stopped out | 56.8% |
| Hit target | 21.2% |

## By setup type

### catch_up
- Trades: **563** | Win: **36.1%** | Avg: **+0.01%** | Median: **-3.39%**

### divergence
- Trades: **113** | Win: **34.5%** | Avg: **-0.08%** | Median: **-2.18%**

## By focus ticker

| Focus | Trades | Win% | Avg% |
|-------|--------|------|------|
| AMD | 48 | 43.8% | +0.98% |
| ASTS | 4 | 25.0% | -2.17% |
| COIN | 138 | 33.3% | +0.11% |
| HOOD | 22 | 40.9% | +0.50% |
| IONQ | 8 | 37.5% | +1.79% |
| JOBY | 21 | 19.0% | -2.58% |
| LUNR | 6 | 66.7% | +6.56% |
| MSTR | 114 | 40.4% | +0.39% |
| NVDA | 100 | 33.0% | -0.54% |
| PLTR | 29 | 48.3% | +0.26% |
| RKLB | 118 | 31.4% | -0.18% |
| SMCI | 25 | 36.0% | -1.09% |
| SOFI | 43 | 34.9% | -0.40% |

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

`data/BACKTEST_SETUPS.csv`

## Reproduce

```bash
python backtest_setups.py --years 1
```
