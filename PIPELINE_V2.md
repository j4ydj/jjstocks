# Pipeline v2 — high-selectivity + unconventional edge

Target **~90% win rate** on in-sample training; live uses **approved trades only** on Telegram.

## What changed

| Layer | Change |
|-------|--------|
| **Direction** | `PIPELINE_FADE_MODE=1` (default): contrarian vs leader move |
| **Filters** | Prior-day leader ≥2%, spread z-score, SPY/QQQ regime, VIX panic gate |
| **Unconventional** | Wikipedia attention, SEC filing risk, global macro chains, residual spread z |
| **Approved layer** | Up to **3** US-liquid trades/day; score ≥ **42** (fallback ≥ **32** so scans rarely show zero) |
| **Telegram** | **4-section simple report** (new / existing / status / summary) |
| **Research file** | Same report at top of `data/latest_pipeline_output.txt`; full correlation dump in appendix |
| **Tier 3** | `paper_portfolio.py` (compound paper P&L), `backtest_approved.py` (live + CSV stats) |

## Unconventional data (not typical scanners)

| Signal | Source | Role |
|--------|--------|------|
| **Spread z** | Pair return residual vs beta | Fade entry when pair is stretched |
| **Wikipedia** | Wikimedia pageviews | Attention before price; confirms or blocks |
| **SEC** | EDGAR 10-K/10-Q phrases | Hard penalty if going concern / material weakness |
| **Macro chains** | ~35 global index ETFs | GLD→EEM→EWY style propagation paths |
| **Playbook** | Walk-forward pair history | Only pairs with proven win rate |

## Env vars

See `pipeline_config.py`. Key toggles:

- `PIPELINE_FADE_MODE=1` — contrarian entries (leave on)
- `PIPELINE_MAX_TRADES=3` — daily cap on Telegram
- `PIPELINE_TARGET_MIN_TRADES=1` — try to surface at least one trade per scan
- `PIPELINE_ACTIONABLE_US=1` — only US-listed liquid names for actionable trades
- `PIPELINE_MIN_ALT_SCORE=42` — min composite unconventional score
- `PIPELINE_FALLBACK_ALT_SCORE=32` — relaxed floor if strict pass is empty
- `PIPELINE_MIN_CORR_ACTIONABLE=0.60` — min |r| for correlation pairs in approved layer
- `SCAN_UNIVERSE=global` — discovery scan; actionable still US-filtered when `PIPELINE_ACTIONABLE_US=1`

## Backtest

```bash
python3 backtest_map_pipeline.py --years 2 --step 5
python3 backtest_approved.py    # approved layer + paper portfolio stats → APPROVED_BACKTEST.md
```

## Live

Railway / cron → `daily_pipeline.py` → Telegram **approved only** + `data/latest_pipeline_output.txt`.

**Manual:** `python3 daily_pipeline.py` (no Telegram) or `/run` in Telegram bot.

**Refresh P&L:**

```bash
python3 correlation_trades.py --refresh --performance
```

## Modules

- `alt_signals.py` — Wikipedia, SEC, macro chain, spread z scoring
- `simple_report.py` — Telegram + file: new / existing / status / summary
- `approved_trades.py` — merge v2 + filtered correlation pairs with fallback selection
- `paper_portfolio.py` — paper equity curve if you took every approved trade
- `correlation_trades.py` — log all |r|≥0.6 for research; outcomes tracked 7d
