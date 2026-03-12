# Why We Can’t Get to 90% (And What We Learned)

## Important caveat

**Earlier conclusions were based on a single test:** one mixed US universe and ~48 signals. We had *not* tested the same strategy across different markets, countries, or stock types. So saying "this is the best we can do" was premature.

**We now test across segments:** run `./venv/bin/python backtest_all_markets.py` to run the same winning strategy on:
- US large cap, US small/mid cap  
- US tech, US healthcare, US financials, US consumer/industrials  
- Canada (TSX / US-listed Canadian), UK (FTSE-style .L)

Results are written to `backtest_cache/all_markets_results.json`. Use them to see which market/country/stock type the strategy is suited to before drawing conclusions.

---

## The Ask

You asked: *why can’t we get it to 90%?*

Interpreted as: **90% win rate** or **90% alpha hit rate** (fraction of trades that beat SPY). This doc explains why that’s not achievable with our setup—and what *is* achievable.

---

## 1. What 90% Would Imply

- **90% win rate** means 9 out of 10 trades make money. On a large, liquid universe with **free, public data**, that would be an enormous edge.
- If such an edge existed, every quant fund and retail screener would trade it until it disappeared. The fact that we’re still testing the same free datasets (yfinance, SEC EDGAR) means the market has already arbitraged the obvious stuff.
- **Renaissance Technologies (Medallion)** is often cited at roughly a **50.75%** win rate—they make money from **expectancy** (size of wins vs losses), not from winning almost every trade. If 90% were reachable with public data, they’d be there.

So: **90% with free data would mean the market is wildly inefficient in a way that contradicts decades of evidence.** We can’t get there without changing the problem (e.g. private data, or a tiny number of hand-picked trades that aren’t a “system”).

---

## 2. Why Our Strategies Cap Out Around 55–60%

### A. **The data is public and lagging**

- **Earnings surprise** is known within minutes of the report. We enter on the **next trading day**. By then, a big chunk of the move is often already in the price. We’re not front-running; we’re trading after the fact.
- **RSI, MACD, volume** are used by everyone. There’s no information advantage. Our backtests showed that adding more technical filters doesn’t push hit rate meaningfully above the mid‑50s.

### B. **One rule for 100 names**

- We apply the **same** rule (e.g. “earnings beat 40–100%”) to a **broad** universe. The edge might exist only in a small subset (e.g. small caps, or one sector), but we dilute it by including everything.
- When we **tighten** (e.g. top 25% by surprise, or 60–100% surprise only), we get **fewer** signals. In our tests, hit rate might go up a few points (e.g. 58% → 62%), but we’re still far from 90%, and we give up sample size (harder to validate, fewer trades per year).

### C. **Regime and time dependence**

- Our “winning” strategy (earnings 40–100%, hold 40d, bull only) had **negative** median alpha in the **first half** of the sample and **positive** in the second. So the “edge” is **regime‑dependent** (e.g. 2022–2024 bull), not a stable 90% across all environments.
- That’s consistent with **overfitting to recent regimes** or **time-varying efficiency**. It doesn’t support a path to 90%.

### D. **What we already tried**

- **200+ variants:** earnings bands, RSI oversold, combo (earnings + RSI), momentum, bull‑only, different hold periods.
- **Best we saw:** ~**59% alpha hit** (combo: earnings beat + RSI ≤ 40, hold 20d). Rest were in the 52–58% range.
- **Extreme selectivity (top 10% by surprise):** we run this in `analyze_why_not_90.py`. In our run, **top quartile and top decile by surprise had *lower* alpha hit (41.7% and 40%)** than the full 40–100% band (56%). So “bigger surprise only” did **not** improve hit rate; it made it worse. That suggests the relationship between surprise size and forward return is not monotonic in our universe. So we **don’t** have a path to 90% by tightening the band **on that single universe**.

- **Testing across markets/countries/stock types:** we had **not** done this when we first concluded “best we can do.” We now run `backtest_all_markets.py`, which runs the same strategy on US large cap, US small/mid cap, US tech, US healthcare, US financials, US consumer/industrials, Canada, and UK. In the first full run:
  - **US consumer & industrials** had the only clearly positive median alpha (+2.27%) and 52.9% alpha hit.
  - **Canada** had 66.7% alpha hit on only 6 signals — suggestive but not enough data.
  - US tech, large cap, financials had **negative** median alpha. So the strategy is **not** equally suited to all segments; it may be better suited to certain sectors/markets. We still have not tested every country or every stock type (e.g. more international exchanges, ETFs, or sectors). Conclusions should be updated as more segments are added and re-run.

So the **ceiling** with our data and methods is in the **low‑to‑mid 60s** for hit rate, not 90%.

---

## 3. What Would Be Needed to Get to 90% (And Why We Don’t Have It)

| Requirement | Why we don’t have it |
|-------------|----------------------|
| **Private or proprietary data** | We use only free, public data (yfinance, SEC). No satellite, credit card, or order-flow data. |
| **Information before the market** | We don’t have faster news, earlier earnings, or insider info. We enter after public information is out. |
| **Tiny, hand-picked trades** | We could take 1–2 trades a year with “maximum conviction” (e.g. 3+ insiders buying + earnings beat + small cap). That might have a higher hit rate but wouldn’t be a **system** with 30+ signals, and 90% still wouldn’t be guaranteed. |
| **Curve-fitting** | We could overfit the backtest until it shows 90%. That would **fail out-of-sample** and in live trading. So it’s not a real 90%. |

So: **90% is not achievable with our current data and a robust, backtested system.** The only way to “get to 90%” would be to change the problem (better data, or a non-system approach) or to cheat (overfit).

---

## 4. Lessons from the Failures

1. **Free data → no durable edge**  
   Anything we can compute (earnings surprise, RSI, volume) is already in the hands of millions of participants. The edge from “better rules” on the same data is small and unstable.

2. **More signals ≠ better**  
   Adding more technical or alternative signals didn’t raise hit rate; it often added noise. **Fewer, higher-conviction** signals (e.g. combo, or top quartile by surprise) **did not** improve hit rate in our test: top quartile / top decile by surprise had **lower** alpha hit than the full 40–100% band. So extreme selectivity on one dimension (surprise size) is not a path to 90%.

3. **Regime matters**  
   Strategies that worked in one half of the sample failed in the other. So we **must** filter by regime (e.g. bull only) or accept that hit rate is time-dependent. That still doesn’t get us to 90%.

4. **Consistency check is essential**  
   Requiring at least one half of the sample to have positive median alpha (and neither half below -5%) prevented us from shipping strategies that looked good on average but were propped up by one good period. That’s a **lesson to keep**: don’t relax consistency to chase a number.

5. **Realistic target**  
   With free data and a diversified universe, a **realistic ceiling** is roughly **55–65%** alpha hit rate and **55–65%** win rate. Our current best strategy sits in that band. Pushing toward 70% might be possible with **very** strict filters (e.g. top 5% by surprise + bull + small cap only), but we’d have very few signals and no guarantee it holds out-of-sample.

---

## 5. What We Can Do Instead of Chasing 90%

- **Maximize expectancy, not hit rate**  
  Aim for **positive median alpha** and **positive average alpha** (with strict consistency and OOS checks). A 55% hit rate with 5% median alpha can be better than a 70% hit rate with 0.5% median alpha if the losing trades are small.

- **Extreme selectivity as an option**  
  Run `analyze_why_not_90.py` to see hit rate when we take only **top 10% or 25%** of signals by surprise (or stricter bands like 60–100%). Use that as a **high-conviction** mode: fewer signals, slightly higher hit rate, same data.

- **Admit the ceiling**  
  Document that with **free data and a systematic, backtested approach**, we do **not** expect to reach 90% win rate or 90% alpha hit rate. Treat anything in the **high 50s to low 60s** as success, and focus on **robustness and expectancy** rather than a headline number.

---

## 6. Bottom Line

- **90% is not achievable** with our current data and a robust system. It would require private information, a different (non-system) approach, or overfitting.
- **We’re stuck around 55–60%** because the data is public, the rules are simple, and the market is efficient enough that the edge is small and regime-dependent.
- **Lessons:** prioritize consistency and out-of-sample checks, use regime filters, prefer fewer high-conviction signals when we want a bit more hit rate, and aim for **expectancy and stability**, not a 90% target.
