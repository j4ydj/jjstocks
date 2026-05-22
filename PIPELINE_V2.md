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

**Manual trigger:** send `/run` in Telegram (only your `TELEGRAM_CHAT_ID`).

## What the scan actually does (500 names)

**Critical:** live scans use 6mo prices (~126 bars). `PIPELINE_MIN_BARS=60` (not 130) or the returns matrix is empty and correlations show as $0 / none.

1. Loads universe from `SCAN_UNIVERSE`:
   - **`global`** (default): ~18 index benchmarks + constituents in `data/indexes/` (~1k+ tickers, batched download)
   - **`us`**: ~518 from `sp500_symbols.txt` + extras
2. **One batch** Yahoo download (6 months) — scores **every** symbol that returned data (~470–490).
3. Picks **top 15** volatile → builds chains (corr / lead-lag) on those only.
4. Pipeline predictions on **top 12** focus names — not 518×518 daily.

Typical runtime **1–3 minutes**, not a full correlation map of the entire market.

If no trades: filters are strict or playbook empty — normal on quiet days.
