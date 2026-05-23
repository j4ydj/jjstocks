# Trade tracking report

> Generated: **2026-05-23 21:34:53**
> Log file: `/Users/home/stocks/data/trade_setups.jsonl`
> CSV: `/Users/home/stocks/data/trade_tracker.csv`

## Summary

| Metric | Value |
|--------|-------|
| Scans logged | 12 |
| Proposed trades | 7 |
| Open | 4 |
| Closed (10d or stop/target) | 3 |
| Closed with 5d outcome | 0/3 wins (0%), avg -4.18% |

## Open trades

| ID | Date | Type | Dir | Ticker | Entry | Stop | Target | Telegram |
|----|------|------|-----|--------|-------|------|--------|----------|
| 20260523213452-IONQ-approved | 2026-05-23 | corr_pair | SHORT | IONQ | $63.64 | $65.80 | $59.32 | no |
| 20260523213452-AMD-approved | 2026-05-23 | corr_pair | SHORT | AMD | $467.51 | $481.41 | $439.71 | no |
| 20260523213452-MPWR-approved | 2026-05-23 | corr_pair | SHORT | MPWR | $1589.81 | $1675.42 | $1418.59 | no |
| 20260523102926-ACHR-approved | 2026-05-23 | corr_pair | SHORT | ACHR | $6.36 | $6.75 | $5.58 | no |

## Closed trades (with outcomes)

| Date | Type | Dir | Ticker | 1d | 5d | 10d | Stop hit | Target hit | Thesis |
|------|------|-----|--------|----|----|-----|----------|------------|--------|
| 2026-05-18 | catch_up | SHORT | RKLB | +2.9% | -3.5% | — | True | False | LUNR -7.2% today; RKLB lagging (-5.9%). Historical… |
| 2026-05-18 | catch_up | SHORT | JOBY | +3.4% | -5.5% | — | True | False | RKLB -5.9% today; JOBY lagging (-2.6%). Historical… |
| 2026-05-18 | catch_up | SHORT | RKLB | +2.9% | -3.5% | — | True | False | RDW +nan% today; RKLB lagging (-5.9%). Historicall… |

## Commands

```bash
python trade_tracker.py --fill     # refresh outcomes
python trade_tracker.py --report   # refresh this file
python chain_ping.py             # one scan (logs trades)
```
