# Research Agenda — What We’ve Done vs What We Haven’t

**How we extend research:** Run experiments from §3 without waiting for a specific ask; document in §5; update winning strategy or docs when something passes or clearly improves. Re-run promising variants on the **full** universe (59+ tickers) when the quick run used a smaller set.

---

## 1. What we’ve actually done and concluded

| Area | Done | Conclusion |
|------|------|------------|
| **Earnings drift** | 200+ configs (surprise bands, hold days, regime) | One passes: 40–100% surprise, hold 40d, bull only. Others don’t. |
| **Technical (RSI, momentum)** | RSI oversold, momentum (SMA50+RSI band) | No edge; median alpha negative. |
| **Combo** | Earnings + RSI ≤40 at entry | No pass. |
| **Diamond (Market Cipher)** | Pure diamond, bull, step, strict -70; diamond+earnings combo; earnings+diamond filter | None pass. Combo 40% surprise has good alpha but n=5. Not used as entry rule. |
| **All segments** | Same winning strategy on 8 segments (cap, sector, country) | Only US_consumer_industrials has clear positive median alpha (52.9% hit). Tech/large/financials negative. |
| **Data** | yfinance only for backtest; data_fetcher with Alpha Vantage fallback added | Rate limits handled by fallback; no other data wired into backtest yet. |

So far we’re **not** doing: walk-forward, Monte Carlo, transaction costs, or alternative data inside the backtest.

---

## 2. Open questions (we haven’t answered)

- **Red/blood diamond as filter:** If we *drop* earnings signals when there was a red or blood diamond in the last N days before entry, does median alpha improve? (We tried “keep only when green diamond after entry” and got 0–2 signals; we didn’t try “exclude when bearish diamond recently”.)
- **Best universe:** Winning strategy was found on a mixed 59-ticker universe. Segment run said consumer_industrials is best. We haven’t run the **exact same strategy** on **only** the consumer_industrials ticker list and reported it as the “recommended universe” with full metrics.
- **Hold period sensitivity:** We use 40d because one config passed. We haven’t run 20, 30, 50, 60 on the same strategy to see if 40 is a local optimum or if 30/50 would be better.
- **Surprise band sensitivity:** We use 40–100%. We haven’t gridded 30–80, 50–120, 40–150 etc. to see robustness.
- **Other modules in backtest:** Squeeze, volume anomaly, insider clusters exist but are **not** in the backtest engine. We don’t know if “earnings + low short interest” or “earnings + insider cluster” would pass (would require caching or loading that data per bar).
- **Regime beyond SPY>SMA200:** No VIX, no yield curve, no FRED in the engine. Research doc mentioned it; not implemented.
- **News/sentiment:** In MARKET_TRACKING_AND_DATA_RESEARCH.md as next step; not integrated. No “only take signal if recent sentiment > X”.

---

## 3. Next experiments that extend the research (in order)

1. **Red/blood diamond as exclusion filter**  
   For each earnings signal (40–100%, bull, 40d), drop it if that ticker had a red or blood diamond in the 5 trading days before entry. Re-run backtest. Report n, median alpha, alpha hit. If alpha improves and n stays ≥30, we have a better rule.

2. **Winning strategy on consumer_industrials-only universe**  
   Use the US_consumer_industrials ticker list from `backtest_all_markets.py`. Run same strategy (40–100%, hold 40d, bull). Report full metrics. If it passes and beats the mixed-universe run, document it as the “recommended universe”.

3. **Hold period sweep**  
   Same strategy, hold_days ∈ {20, 30, 40, 50, 60}. Table: hold_days, n, median_alpha, alpha_hit. See if 40 is best or if 30/50 is better.

4. **Surprise band sweep**  
   Same strategy, (min_surprise, max_surprise) ∈ {(30,80), (40,100), (50,120), (40,150)}. Table: band, n, median_alpha, alpha_hit. Check robustness.

5. **Earnings + volume anomaly (if feasible)**  
   Add volume spike detection to backtest (e.g. volume > 2× 20d avg on entry day). Filter: keep only earnings signals where volume is elevated. Requires volume in cache (we have it). Quick to add and run.

6. **Walk-forward mention**  
   Document that current backtest is single in-sample period; a proper walk-forward (train 2019–2022, test 2023, roll) is not implemented. Add as “future work” and optionally a stub script.

7. **FRED regime (optional)**  
   Add optional regime filter: only enter when VIX < 25 or 10Y–2Y > 0. Requires FRED API and aligning dates; lower priority than 1–4.

---

## 4. What “thinking for yourself” means here

- **Do** run experiments 1–4 (and 5 if trivial) and document results in this repo.
- **Do** update this agenda when we run new tests or get new data sources.
- **Don’t** add more signal types without backtesting them and reporting pass/fail.
- **Don’t** assume the first passing strategy is the best; sweep parameters and universes.

The next section below will be updated with **results** from the experiments above as we run them.

---

## 5. Experiment results

### 5.1 Red/blood diamond as exclusion filter  
**Run:** Same strategy (40–100%, hold 40d, bull), but drop any entry where that ticker had a red or blood diamond in the 5 trading days before entry.  
**Result (32-ticker universe):** Baseline n=10, med_alpha=0.40%, alpha_hit=50%. With exclusion: n=9, **med_alpha=+7.12%**, **alpha_hit=55.6%**. So excluding “bearish diamond recently” improved the cohort; did not pass only because n&lt;30. **Worth using on larger universe** to see if it passes with more signals.

### 5.2 Consumer_industrials-only universe  
**Run:** Same strategy on US_consumer_industrials ticker list only.  
**Result:** n=9, med_alpha=-0.66%, alpha_hit=44.4%. On this run not better than mixed universe. (Earlier all_markets run had consumer_industrials +2.27% on 17 signals—different universe/setup.)

### 5.3 Hold period sweep  
**Run:** Same strategy, hold_days ∈ {20, 30, 40, 50, 60}.  
**Result:** Best is **hold=30**: med_alpha **+8.83%**, alpha_hit **70%**. Next hold=20: +5.85%, 60%. hold=40 was +0.40%, 50%. So **30d (or 20d) may be better than 40d** on this universe; 40d was from original 59-ticker pass. Re-run on full universe to confirm.

### 5.4 Surprise band sweep  
**Run:** (min_surprise, max_surprise) ∈ {(30,80), (40,100), (50,120), (40,150)}.  
**Result:** 40–100% was best (0.40%, 50%). Other bands worse. **40–100% is robust** in this sweep.

### 5.5 Earnings + volume filter  
*Pending.*

### 5.6 Path to 80% alpha hit  
**Done.** User asked to aim for at least 80%. We added `earnings_top_pct_surprise` filter, `search_80.py`, and ran 100 strict configs (bull + no red diamond + top 10/25/33/50% by surprise, hold 20/30, surprise bands 40–100% up to 80–100%). **Result:** best **66.7%** alpha hit with n=6 (top 10%, hold 20d). No config reached 80% with n≥10. Documented in `PATH_TO_80.md`. **Aggressive mode** added to `run_winning_strategy.py --mode aggressive` (hold 20d, top 25% by surprise) for fewer, higher-conviction signals.
