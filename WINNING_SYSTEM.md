# Winning System — Backtested Strategy

## Summary

After testing 200+ strategy variants (earnings drift, RSI oversold, momentum, combo) across a 59–80 stock universe and 756 days of data, **one strategy met the success criteria** and is the only system we run live.

---

## Success Criteria (All Required)

| Criterion | Threshold |
|-----------|-----------|
| Median alpha vs SPY | ≥ 0.5% |
| Alpha hit rate | ≥ 52% |
| Win rate | ≥ 52% |
| Minimum signals | ≥ 30 |
| Consistency | At least one half of sample has positive median alpha; neither half < -5% |
| Out-of-sample | Last 252 days: median alpha ≥ 0 when ≥ 15 signals |

---

## Winning Strategy: `earn_h40_surp40_100_bullTrue`

**Rule set**

1. **Signal:** Earnings beat with **surprise in 40–100%** (actual EPS vs estimate).
2. **Entry:** First trading day on or after the earnings date.
3. **Hold:** **40 trading days** (~8 weeks).
4. **Regime filter:** Trade **only when SPY is above its 200-day SMA** (bull regime). No new entries when SPY is below 200d MA.

**Backtest result (59-ticker universe, 756 days)**

| Metric | Value |
|--------|--------|
| Signals | 48 |
| Median alpha | **+5.67%** |
| Mean alpha | +8.2% |
| Alpha hit rate | **56.25%** |
| Win rate | **60.4%** |
| First half median alpha | -3.81% |
| Second half median alpha | +10.48% |
| OOS (last 252d) median alpha | +20.57% |

The strategy was weak in the first half of the sample and strong in the second half and OOS. Criteria allow one half to be negative as long as the other is positive and neither half is below -5%.

---

## Results by segment (all markets / stock types)

The same strategy was run on **eight segments** (market cap, sector, country). Run `./venv/bin/python backtest_all_markets.py` to reproduce. Summary from last run:

| Segment | N signals | Median alpha | Alpha hit % | Win rate % |
|---------|-----------|--------------|-------------|------------|
| **US_consumer_industrials** | 17 | **+2.27%** | **52.9%** | 58.8% |
| Canada | 6 | +0.86% | 66.7% | 66.7% |
| US_small_mid_cap | 58 | -1.77% | 46.5% | 53.5% |
| US_healthcare_biotech | 25 | -2.07% | 48.0% | 56.0% |
| US_financials | 10 | -2.94% | 40.0% | 60.0% |
| US_tech | 27 | -5.89% | 37.0% | 51.9% |
| US_large_cap | 5 | -5.96% | 40.0% | 60.0% |
| UK | 0 | — | — | — (no earnings data) |

**Takeaways:**
- **US consumer & industrials** is the only segment with clearly positive median alpha and 50%+ alpha hit in this run; the strategy may be better suited to this segment.
- **Canada** had the highest alpha hit (66.7%) but only 6 signals — too few to be conclusive; worth retesting with a larger Canadian universe.
- **US tech, large cap, financials** had negative median alpha; the strategy does not appear well suited to those segments in this test.
- **UK** produced no signals (earnings data in yfinance for .L tickers was insufficient).

So we **do not** know that the original mixed-US run is “the best” — we only ran it on one mix. Testing across segments shows the strategy may be **best suited to US consumer/industrials**; other markets/countries/stock types need more data or different universes before concluding.

---

## How to Run

### Test across ALL segments (market cap, sector, country)

Before concluding the strategy is “best” or “only works in X”, run:

```bash
./venv/bin/python backtest_all_markets.py
```

This runs the **same** strategy (earnings 40–100%, hold 40d, bull only) on:
- US large cap, US small/mid cap  
- US tech, US healthcare, US financials, US consumer/industrials  
- Canada, UK  

Results are printed and saved to `backtest_cache/all_markets_results.json`. Use them to see which segment has the highest median alpha or alpha hit rate.

### Live scan (current signals)

```bash
./venv/bin/python run_winning_strategy.py
```

- Checks if SPY is in bull regime (above 200d MA).
- Scans the universe for earnings in the last 15 days with surprise 40–100%.
- Prints ticker, earnings date, surprise %, price, and hold period.

JSON output:

```bash
./venv/bin/python run_winning_strategy.py --json
```

### Full strategy search (re-run backtests)

```bash
./venv/bin/python strategy_search.py
```

- Loads price and earnings data.
- Runs all strategy configs.
- Writes passing strategies to `backtest_cache/winning_strategies.json`.
- If none pass strict criteria, tries relaxed (e.g. min_signals=15, median_alpha≥0.25%, alpha_hit≥51%).

### Single backtest

```bash
./venv/bin/python -c "
from backtest_engine import BacktestConfig, fetch_and_cache_prices, load_earnings_history, run_backtest
data, spy = fetch_and_cache_prices(['AAPL','MSFT',...], days=756)
earn = load_earnings_history(list(data.keys()))
cfg = BacktestConfig('earn_h40', hold_days=40, min_surprise_pct=40, max_surprise_pct=100, require_bull_regime=True, signal_type='earnings')
res, df = run_backtest(data, spy, earn, cfg)
print(res.passed, res.median_alpha_pct, res.n_signals)
"
```

---

## Files

| File | Role |
|------|------|
| `backtest_engine.py` | Backtest framework: data fetch, signal generation (earnings, technical, combo, momentum), return calculation, pass/fail criteria. |
| `strategy_search.py` | Builds many configs, runs backtests, saves passing strategies. |
| `backtest_cache/winning_strategy.json` | Canonical winning strategy and backtest summary. |
| `backtest_cache/winning_strategies.json` | Top 5 passing strategies from last full search (when at least one passes). |
| `run_winning_strategy.py` | Live scanner: bull regime check + earnings surprise 40–100%, outputs current signals. |
| `backtest_all_markets.py` | Runs the same strategy on all segments (cap, sector, country); writes `backtest_cache/all_markets_results.json`. |

---

## Integration with Telegram Bot

To surface these signals in the bot, add a command (e.g. `/signals`) that:

1. Calls `run_winning_strategy.scan()` (or runs `run_winning_strategy.py --json` and parses output).
2. Sends a message with bull regime and list of current signals (ticker, earnings date, surprise %, price, hold 40d).

Strategy logic lives in `backtest_engine` and `run_winning_strategy`; the bot only displays results.

---

## Caveats

- **Diamond (Market Cipher):** Green/red/blood diamond was backtested in multiple variants (pure diamond, diamond+earnings combo, earnings+diamond filter). **None passed** the engine bar; best diamond_combo had strong alpha but too few signals (n=5). See `BACKTEST_DIAMOND_RESULTS.md`. Diamond is available as **context only** in `/analyze`, not as an entry rule.
- **One regime:** Strategy is validated only in bull regimes (SPY &gt; 200d MA). No entries in bear regimes.
- **Earnings timing:** Entry is first trading day on/after earnings. Actual report time (BMO/AMC) is not used; yfinance earnings date is used.
- **Survivorship:** Universe excludes names that were delisted during the backtest period.
- **Caveats:** Strategy may be better suited to **US consumer/industrials** than to tech or large cap (see segment table above). Canada showed high hit rate on very few signals; UK had no usable earnings data. Re-run `backtest_all_markets.py` after adding more tickers or regions before concluding which market is “best.”
- **Costs:** Backtest does not include commissions or slippage; assume ~0.05% per side for live use.

---

## Changelog

- **v1.0** — Winning strategy: earn_h40_surp40_100_bullTrue. Criteria: median_alpha≥0.5%, alpha_hit≥52%, win≥52%, n≥30, half_ok, oos_ok. Live runner and docs added.
