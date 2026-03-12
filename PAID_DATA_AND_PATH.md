# Paid Data Sources & Another Path to Higher Hit Rate

**Purpose:** Find non-free data sources that could give a **different path** toward 80%+ alpha hit rate, and outline how to integrate them.

---

## 1. Why Paid Data Can Be a Different Path

- **Free data** (yfinance, SEC EDGAR, etc.) is the same for everyone; we capped at ~67% alpha hit with maximum selectivity.
- **Paid data** can provide:
  - **Faster or deeper fundamentals** (earnings timestamps, better surprise/estimate data)
  - **Options flow / dark pool** (unusual activity before moves)
  - **News sentiment** (institutional-grade, entity-level)
  - **Better price quality** (real-time or lower-latency, fewer gaps)

So the "other path" is: **add one or more paid feeds, backtest the same strategy (or strategy + paid filter), and see if hit rate or median alpha improves.**

---

## 2. Paid Data Sources by Category

### 2.1 Price & OHLCV (better than yfinance)

| Provider | Pricing | What you get | Why it helps |
|----------|---------|--------------|--------------|
| **Polygon.io (Massive)** | Free tier; **$29/mo** Starter (15min delay, 5yr history); **$79/mo** Developer (trades, 10yr); **$199/mo** Advanced (real-time) | US stocks, aggregates, corporate actions, WebSockets | Fewer rate limits, more history, optional real-time for entry timing. |
| **Tiingo** | Free (500 symbols/mo, 50 req/hr); **$30/mo** Power (100k req/day, 40GB); **$50/mo** Business | EOD + real-time, 30yr history, fundamentals add-on (contact) | Simple API, good for backfill and live; fundamentals add-on for better earnings. |
| **Intrinio** | EOD historical **$3,100/yr**; Tick history **$6,000/yr**; EquitiesEdge real-time **$1,250/mo** | 50+ years EOD; tick for backtesting | Institutional-grade; expensive for solo. |
| **Marketstack** | **$9.99/mo** Basic (10k req/mo); **$49.99/mo** Pro (100k); **$149.99/mo** Business (500k) | EOD global, 30+ years | Cheap; good fallback or supplement. |

**Practical pick for “another path”:** **Polygon Starter ($29/mo)** or **Tiingo Power ($30/mo)** for reliable OHLCV + longer history and no yfinance rate-limit issues. Use as primary in `data_fetcher` when key is set.

---

### 2.2 Earnings, Estimates & Surprise (better than yfinance)

| Provider | Pricing | What you get | Why it helps |
|----------|---------|--------------|--------------|
| **Alpha Vantage Premium** | **$49.99–249.99/mo** (75–1,200 req/min); annual $499–2,499 | Earnings calendar, real-time, US options | Higher rate limits, earnings + options in one place. |
| **Earnings API** | Contact / usage-based | Calendar-first, reporting time (BMO/AMC), summaries | Optimized for speed and structure; good for entry timing. |
| **Refinitiv I/B/E/S (LSEG)** | Enterprise (contact) | 56k+ companies, 900+ firms, **StarMine SmartEstimates®** (better predictor of surprise), actual surprise metrics | Institutional standard; **better surprise definition** and leading indicators. Too expensive for most retail. |
| **Intrinio** | Fundamentals **$9,600/yr**; earnings-related in bundles | Fundamentals + estimates | Mid-tier institutional. |

**Practical pick:** **Alpha Vantage Premium** ($50–100/mo) for more robust earnings + higher limits; or **Tiingo** fundamentals add-on (contact) if already using Tiingo for price. Refinitiv is the “best” path for earnings quality but is enterprise-priced.

---

### 2.3 Options Flow & Dark Pool (no free equivalent)

| Provider | Pricing | What you get | Why it helps |
|----------|---------|--------------|--------------|
| **Unusual Whales** | **$32/mo** (15min delay) or **$42/mo** (live); API on top of subscription | Options flow, sweeps/blocks, dark pool, sentiment, congressional trading | **Different path:** filter earnings signals: only take when unusual flow agrees (e.g. call buying in same ticker around event). |
| **Intrinio Options** | **$2,500/mo** real-time; **$9,600/yr** 15min delayed; **$2,800/yr** EOD historical | Filtered OPRA, Greeks, unusual activity | Full options backtesting; expensive. |
| **OptionData.io** | Contact | Smart option flow, sweeps, anomalies | Alternative to Unusual Whales. |

**Practical pick:** **Unusual Whales $32–42/mo** (subscription + API). Use as a **filter**: e.g. “only take earnings 40–100% signal if Unusual Whales shows bullish flow in that ticker in last 1–5 days.” Backtest by logging flow at signal time (if API allows historical or we collect live) and then test “earnings + flow filter” in backtest.

---

### 2.4 News & Sentiment (institutional-grade)

| Provider | Pricing | What you get | Why it helps |
|----------|---------|--------------|--------------|
| **APITube News API** | **$99/mo** (20k req); up to **$599/mo** enterprise | 300k+ sources, real-time | Entity-level sentiment for tickers. |
| **Bloomberg / Refinitiv** | Enterprise (contact) | News analytics, sentiment, 220k+ entities (Bloomberg); Reuters + NLP (Refinitiv) | Best quality; not realistic for retail. |
| **Alpha Vantage / Finnhub** | Free tiers; AV Premium for higher limits | News + sentiment endpoints | We can use free first; paid for volume. |

**Practical pick:** Start with **Finnhub** or **Alpha Vantage** free sentiment; if we need more volume or quality, **APITube $99/mo** or **Alpha Vantage Premium** for news.

---

### 2.5 Other (satellite, job postings, etc.)

- **Satellite (Planet, ICEYE, SkyFi, Sentinel Hub):** paid tiers for programmatic access; high effort to turn into a signal; long-term “other path” only.
- **Job postings (Apify, ScrapingBee, HasData):** pay-per-call or ~$49/mo; we already have JobSpy (free) for a first pass.
- **sec-api.io:** paid for full-text SEC search; useful for risk/event filters.

---

## 3. Concrete “Other Path” Using Paid Data

### Path A: Better price + earnings (minimal paid)

1. **Add Polygon.io or Tiingo as primary price source** when API key is set (e.g. in `data_fetcher` and backtest).
2. **Use same strategy** (earnings 40–100%, bull, hold 20/40d, optional top % by surprise).
3. **Compare backtest:** same universe, same rules, Polygon/Tiingo data vs yfinance. If paid data has fewer gaps or better timestamps, we may see different (hopefully better) hit rate or median alpha.
4. **Cost:** **$29–30/mo.**

### Path B: Options flow as filter (paid)

1. **Subscribe to Unusual Whales** ($32 or $42/mo) and use their API.
2. **New module:** `options_flow_filter.py` — for a given ticker and date, query “was there unusual call buying (or bullish flow) in the last N days?” (or use live flow and log it for future backtest).
3. **Strategy:** Keep only earnings signals (40–100%, bull, hold 20d) where flow filter returns “bullish” (or “not bearish”). Backtest if we can get historical flow or build a forward log.
4. **Cost:** **$32–42/mo.** Hypothesis: earnings + flow confirmation could push hit rate toward 70%+.

### Path C: Better earnings + options (combined paid)

1. **Alpha Vantage Premium** ($50–100/mo) for earnings + higher limits.
2. **Unusual Whales** ($32–42/mo) for options flow.
3. **Pipeline:** Price from AV or yfinance → Earnings from AV → Flow from Unusual Whales → filter: surprise 40–100%, bull, flow bullish, hold 20d.
4. **Cost:** **~$80–140/mo.** Test whether “better surprise definition” + “flow confirmation” improves hit rate vs free-only.

### Path D: Institutional-grade surprise (enterprise)

1. **Refinitiv I/B/E/S** (via LSEG Refinitiv Data Platform) for StarMine SmartEstimates and actual surprise metrics.
2. **Strategy:** Same logic (bull, hold) but use Refinitiv’s surprise and estimates; optionally add their predicted surprise as a filter.
3. **Cost:** Enterprise (contact). Only if you have budget and want the “best” earnings path.

---

## 4. Integration Plan (Code)

- **`data_fetcher.py`:** Add optional **Polygon** and **Tiingo** backends. If `POLYGON_API_KEY` or `TIINGO_API_KEY` is set, use them for `get_stock_history()` and/or `fetch_prices_bulk()` (with yfinance fallback when key missing or request fails).
- **`options_flow_filter.py` (new):** Thin client for Unusual Whales API (or similar): `is_bullish_flow(ticker, lookback_days)` or `get_flow_summary(ticker)`. Used in `run_winning_strategy` as optional filter when `UNUSUAL_WHALES_API_KEY` (or subscription) is set.
- **Backtest:** For Path A, run existing backtest with data from Polygon/Tiingo when keys are set. For Path B/C, we need either historical flow data or a forward log; document “flow filter” as live-only until we have history.
- **Config:** In `trading_config.json` or env: `POLYGON_API_KEY`, `TIINGO_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `UNUSUAL_WHALES_API_KEY` (or equivalent). Document in README or this doc.

---

## 5. Summary Table: Paid Sources & Path

| Goal | Source | Rough cost | Action |
|------|--------|------------|--------|
| No rate limits, better OHLCV | Polygon Starter or Tiingo Power | $29–30/mo | Add to data_fetcher; rerun backtest. |
| Better earnings / more limits | Alpha Vantage Premium | $50–100/mo | Use for earnings in scan + backtest. |
| Options flow as filter | Unusual Whales | $32–42/mo | New options_flow_filter; filter earnings signals. |
| Best earnings/surprise | Refinitiv I/B/E/S | Enterprise | Only if budget allows. |
| News sentiment (scalable) | APITube or AV Premium | $99/mo or in AV | Optional filter or feature. |

**Recommended “other path”:** Start with **Path A** (Polygon or Tiingo) to stabilize data and rerun backtest; then add **Path B** (Unusual Whales) as a filter and test live (and backtest when/if historical flow is available). That gives two concrete, paid-data paths without enterprise spend.

---

## 6. Next Steps

1. **Implement Polygon and/or Tiingo in `data_fetcher`** (optional backends when key present).
2. **Document** required env vars and where to get API keys (with links to pricing pages).
3. **Add `options_flow_filter.py`** stub and Unusual Whales (or similar) client; wire into `run_winning_strategy` as `--filter flow` when key is set.
4. **Run backtest** with Polygon/Tiingo data (Path A) and report hit rate vs yfinance baseline.
5. **Log flow** for signals (Path B) so we can later backtest “earnings + flow filter” when we have enough history.

---

## 7. Implemented (This Repo)

- **`data_fetcher.py`** — Polygon and Tiingo optional backends. If `POLYGON_API_KEY` or `TIINGO_API_KEY` is set, `get_stock_history()` tries them before yfinance (order: Polygon → Tiingo → yfinance → Alpha Vantage). Use `prefer_paid=False` to skip paid.
- **`options_flow_filter.py`** — Stub for Unusual Whales API. Set `UNUSUAL_WHALES_API_KEY` when you have a subscription. Update endpoint/response parsing to match their real API.
- **Env vars:** `POLYGON_API_KEY`, `TIINGO_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `UNUSUAL_WHALES_API_KEY`.
