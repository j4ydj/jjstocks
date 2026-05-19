# Pipeline v2 — high-selectivity mode

Target **~90% win rate** on in-sample training; out-of-sample will be lower until forward log validates.

## What changed

| Layer | Change |
|-------|--------|
| **Direction** | `PIPELINE_FADE_MODE=1` (default): contrarian vs leader move — backtest ~81% vs ~21% momentum |
| **Filters** | Prior-day leader ≥2%, spread z-score, SPY/QQQ regime, VIX panic gate |
| **Risk** | Net of 10bps/side, 2-day time stop, spread-z stop, partial 1R |
| **Portfolio** | Max 2 trades/scan, 1 per theme |
| **Playbook** | Whitelist pairs with ≥90% train win when enough samples exist |
| **Schedule** | Scan **21:00 UTC** (after US cash close) |

## Env vars

See `pipeline_config.py`. Key toggles:

- `PIPELINE_FADE_MODE=1` — contrarian entries (leave on)
- `PIPELINE_TARGET_WIN_RATE=90` — playbook whitelist threshold
- `PIPELINE_MAX_TRADES=2` — daily cap

## Backtest

```bash
python3 backtest_map_pipeline.py --years 2 --step 5
```

Outputs: `BACKTEST_PIPELINE_RESULTS.md`, `data/BACKTEST_PIPELINE_TRADES_V2.csv`, `data/pair_playbook.json`

## Live

Railway runs `daily_pipeline.py` → Telegram + `data/trade_setups.jsonl`.

If no trades: filters are strict or playbook empty — normal on quiet days.
