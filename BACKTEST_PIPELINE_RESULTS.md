# Map pipeline backtest — validation results

> Generated: **2026-05-18 12:35:06**
> Period: **2y** | Step: every **5** trading days
> Focus per signal: **12** | Corr window: **60d**

## Executive summary

This backtests the **same engine** that powers the automated daily pipeline:
multi-horizon correlations, chain paths, predicted move %, expected date, entry/stop/target.

| Metric | Value |
|--------|-------|
| Simulated trades | 551 |
| Win rate (P&L) | **44.1%** |
| Direction prediction accuracy | **52.5%** |
| Avg return / trade | **+0.34%** |
| Median return | **-1.22%** |
| Sum of returns (not compounded) | +184.80% |
| Stopped out | 40.8% |

## By prediction type

- **direct_follow**: n=551, win=44.1%, dir_acc=52.5%, avg=+0.34%

## Compare to older backtests

- `BACKTEST_SETUPS_2Y.csv` — narrow chain rules (~37% win)
- `BACKTEST_SETUPS_ADAPTIVE.csv` — filtered narrow rules (~35% win)
- **This file** — map-based pipeline with chain paths


## Last 50 trades

| Signal | Focus | Type | Dir | Leader | Predicted | Actual | Ret% | Dir OK |
|--------|-------|------|-----|--------|-----------|--------|------|--------|
| 2026-03-20 | EXPE | direct_follow | SHORT | CVNA | -4.5% | +5.3% | +5.6% | ✗ |
| 2026-03-20 | GLW | direct_follow | SHORT | FCX | -2.7% | -5.0% | -4.7% | ✓ |
| 2026-03-20 | GLW | direct_follow | BUY | CIEN | +2.5% | -5.0% | -5.0% | ✗ |
| 2026-03-20 | EXPE | direct_follow | SHORT | CIEN | -2.5% | +5.3% | +5.6% | ✗ |
| 2026-03-20 | CF | direct_follow | BUY | IP | -2.4% | -5.0% | -5.0% | ✓ |
| 2026-03-20 | ARES | direct_follow | SHORT | BEN | -2.3% | +1.5% | +1.5% | ✗ |
| 2026-03-20 | APP | direct_follow | SHORT | COIN | -2.3% | -5.1% | -4.8% | ✓ |
| 2026-03-20 | CF | direct_follow | BUY | CCL | -2.2% | -5.0% | -5.0% | ✓ |
| 2026-03-27 | CNC | direct_follow | BUY | FICO | +2.9% | -5.3% | -5.3% | ✗ |
| 2026-03-27 | FICO | direct_follow | BUY | BSX | +1.4% | +6.9% | +6.9% | ✓ |
| 2026-04-06 | CIEN | direct_follow | BUY | INTC | +5.3% | -4.9% | -4.9% | ✗ |
| 2026-04-06 | GLW | direct_follow | BUY | INTC | +5.3% | +10.0% | +10.0% | ✓ |
| 2026-04-06 | GLW | direct_follow | BUY | CIEN | +4.2% | +10.0% | +10.0% | ✓ |
| 2026-04-06 | FIX | direct_follow | BUY | CIEN | +4.2% | +10.0% | +10.0% | ✓ |
| 2026-04-06 | FIX | direct_follow | BUY | GLW | +2.8% | +10.0% | +10.0% | ✓ |
| 2026-04-06 | HPE | direct_follow | BUY | GLW | +2.8% | +0.3% | +0.3% | ✓ |
| 2026-04-06 | JBL | direct_follow | BUY | GLW | +2.8% | +9.9% | +9.9% | ✓ |
| 2026-04-06 | FIX | direct_follow | BUY | FCX | +2.5% | +10.0% | +10.0% | ✓ |
| 2026-04-13 | AXON | direct_follow | SHORT | ADSK | -3.9% | -5.0% | -4.8% | ✓ |
| 2026-04-13 | AXON | direct_follow | SHORT | DDOG | -3.9% | -5.0% | -4.8% | ✓ |
| 2026-04-13 | EL | direct_follow | BUY | CF | -3.2% | +8.1% | +8.1% | ✗ |
| 2026-04-13 | CIEN | direct_follow | BUY | INTC | +2.8% | -5.0% | -5.0% | ✗ |
| 2026-04-13 | GLW | direct_follow | BUY | INTC | +2.8% | -5.0% | -5.0% | ✗ |
| 2026-04-13 | ANET | direct_follow | BUY | INTC | +2.8% | +10.1% | +10.1% | ✓ |
| 2026-04-13 | AXON | direct_follow | SHORT | CSGP | -2.3% | -5.0% | -4.8% | ✓ |
| 2026-04-13 | CIEN | direct_follow | BUY | ETN | +2.3% | -5.0% | -5.0% | ✗ |
| 2026-04-20 | AKAM | direct_follow | BUY | DELL | +5.3% | -0.1% | -0.1% | ✗ |
| 2026-04-20 | CIEN | direct_follow | BUY | AMD | +4.7% | -5.0% | -5.0% | ✗ |
| 2026-04-20 | AKAM | direct_follow | BUY | CHTR | +4.3% | -0.1% | -0.1% | ✗ |
| 2026-04-20 | FICO | direct_follow | BUY | AKAM | +4.3% | -5.1% | -5.1% | ✗ |
| 2026-04-20 | CIEN | direct_follow | BUY | INTC | +3.3% | -5.0% | -5.0% | ✗ |
| 2026-04-20 | CIEN | direct_follow | BUY | ANET | +2.6% | -5.0% | -5.0% | ✗ |
| 2026-04-20 | AKAM | direct_follow | BUY | FICO | +2.3% | -0.1% | -0.1% | ✗ |
| 2026-04-20 | AKAM | direct_follow | BUY | FTNT | +2.1% | -0.1% | -0.1% | ✗ |
| 2026-04-27 | FCX | direct_follow | SHORT | CRL | -5.5% | +9.4% | +10.3% | ✗ |
| 2026-04-27 | FCX | direct_follow | SHORT | IQV | -5.0% | +9.4% | +10.3% | ✗ |
| 2026-04-27 | AXON | direct_follow | SHORT | ADSK | -3.8% | -4.3% | -4.1% | ✓ |
| 2026-04-27 | FICO | direct_follow | SHORT | ACN | -3.7% | -5.0% | -4.8% | ✓ |
| 2026-04-27 | HOOD | direct_follow | SHORT | APP | -3.7% | +10.1% | +11.2% | ✗ |
| 2026-04-27 | HOOD | direct_follow | SHORT | GEN | -3.5% | +10.1% | +11.2% | ✗ |
| 2026-04-27 | HOOD | direct_follow | SHORT | BX | -3.4% | +10.1% | +11.2% | ✗ |
| 2026-04-27 | AXON | direct_follow | SHORT | HOOD | -3.3% | -4.3% | -4.1% | ✓ |
| 2026-05-04 | GLW | direct_follow | BUY | CIEN | +6.6% | +12.4% | +12.4% | ✓ |
| 2026-05-04 | GNRC | direct_follow | BUY | CAT | +5.9% | +4.4% | +4.4% | ✓ |
| 2026-05-04 | GLW | direct_follow | BUY | CAT | +5.9% | +12.4% | +12.4% | ✓ |
| 2026-05-04 | GEV | direct_follow | BUY | CAT | +5.9% | +0.1% | +0.1% | ✓ |
| 2026-05-04 | CIEN | direct_follow | BUY | CAT | +5.9% | +7.7% | +7.7% | ✓ |
| 2026-05-04 | GEV | direct_follow | BUY | GLW | +4.9% | +0.1% | +0.1% | ✓ |
| 2026-05-04 | CIEN | direct_follow | BUY | GLW | +4.9% | +7.7% | +7.7% | ✓ |
| 2026-05-04 | GLW | direct_follow | BUY | EME | +4.2% | +12.4% | +12.4% | ✓ |

## Full trade log

`data/BACKTEST_PIPELINE_TRADES.csv`

```bash
python backtest_map_pipeline.py --years 2
```
