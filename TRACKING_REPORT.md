# Trade tracking report

> Generated: **2026-05-18 11:32:55**
> Log file: `/Users/home/stocks/data/trade_setups.jsonl`
> CSV: `/Users/home/stocks/data/trade_tracker.csv`

## Summary

| Metric | Value |
|--------|-------|
| Scans logged | 1 |
| Proposed trades | 6 |
| Open | 6 |
| Closed (10d or stop/target) | 0 |

## Open trades

| ID | Date | Type | Dir | Ticker | Entry | Stop | Target | Telegram |
|----|------|------|-----|--------|-------|------|--------|----------|
| 20260518113233-RKLB-cat | 2026-05-18 | catch_up | SHORT | RKLB | $124.77 | $133.18 | $107.95 | no |
| 20260518113233-JOBY-cat | 2026-05-18 | catch_up | SHORT | JOBY | $10.36 | $10.88 | $9.32 | no |
|  | 2026-05-18 | catch_up | SHORT | RKLB | $124.77 | $133.18 | $107.95 | no |
|  | 2026-05-18 | catch_up | SHORT | JOBY | $10.36 | $10.88 | $9.32 | no |
|  | 2026-05-18 | catch_up | SHORT | RKLB | $124.77 | $133.18 | $107.95 | no |
|  | 2026-05-18 | catch_up | SHORT | JOBY | $10.36 | $10.88 | $9.32 | no |

## Closed trades (with outcomes)

_No closed trades yet — outcomes fill after 1–10 days. Run `python trade_tracker.py --fill`._


## Commands

```bash
python trade_tracker.py --fill     # refresh outcomes
python trade_tracker.py --report   # refresh this file
python chain_ping.py             # one scan (logs trades)
```
