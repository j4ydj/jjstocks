# Phase 2: Signal quality & validation

Maps your B/B+ review to what was implemented.

## Changes

| Review point | Implementation |
|--------------|----------------|
| 21d window fragile | **`CORR_LOOKBACK_DAYS=60`** default; price history **`6mo`** |
| Weak correlations | **`MIN_CORR_ABS=0.55`** + drop if **p > 0.05** (n≥20) |
| ARKK/SMH repeated | **Macro buckets** — one name per bucket in alerts |
| Lead/lag untested | **`lead_lag_hit_rate`** on each link; **`python lead_lag_backtest.py`** |
| No performance log | **`data/chain_signals.jsonl`** via `signal_log.py` |
| Opposite today unused | **`chain_actions.py`** → "Action hints" in Telegram |
| Regime break | **`regime_break`** flag when 10d vs 60d corr diverges |
| Not a trading system | Hints only (entry/stop/sizing still manual — next phase) |

## Environment

```bash
CORR_LOOKBACK_DAYS=60    # correlation + lag window
MIN_CORR_ABS=0.55        # minimum |r| to keep a link
MIN_CORR_PVALUE=0.05     # require significance when n≥20
MIN_PEER_CORR=0.55       # chain_ping peer display
MIN_MACRO_CORR=0.55      # chain_ping macro display
```

## Commands

```bash
# Forward hit rates (validates predictions)
python lead_lag_backtest.py
python lead_lag_backtest.py --tickers RKLB,DDOG,SMCI

# Log + fill outcomes on past alerts
python signal_log.py

# Full smoke test + Telegram
python test_system.py
python generate_verification.py
```

## Interpreting alerts

- **`r60 +0.88, together; leads ~2d; fwd 62%`** — 60-day correlation, timing, forward hit rate over historical leader moves.
- **`regime⚠`** — recent correlation broke vs 60d; treat link cautiously.
- **`Action hints`** — divergence, validated leaders, or “green on red day” macro conflict (not auto-orders).

## Sample forward validation (2026-05-17)

```
RKLB:
  ARKK → RKLB: corr=+0.60 same day | forward hit: 89.0% over 73 events
  SMH → RKLB: corr=+0.50 same day | forward hit: 75.4% over 61 events
  USO → RKLB: corr=-0.13 leads ~2d | forward hit: 52.0% (noise — below min |r|)

DDOG:
  ARKK → DDOG: corr=+0.30 same day | forward hit: 71.2% (below min |r| now filtered)
```

Links below **|r| 0.55** no longer appear in Telegram; backtest CLI still shows weaker pairs for research.

## Still open (phase 3)

- Hard **entry / exit / stop** rules wired to broker or paper account
- **Portfolio-level** cap on correlated macro exposure
- Walk-forward **out-of-sample** report automated weekly
- Full **position sizing** (ATR-based exists in `trade_levels.py`, not wired to chain path)
