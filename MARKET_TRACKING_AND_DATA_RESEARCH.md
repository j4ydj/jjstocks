# Market Tracking, Bloomberg-Style Tools & Unconventional Data — Full Research

**Purpose:** Answer “have we done full research on all available options?” — TradingView-style indicators (e.g. Blood Diamond), Bloomberg Terminal–like functionality, and data that’s not generally used or available.

---

## 1. TradingView & “Blood Diamond”–Style Indicators

### What “Blood Diamond” Actually Is

- **OpenCipher A** (TradingView, by RealMarketMaker) is an open-source overlay that combines:
  - **EMA ribbon:** 8 EMAs (5, 11, 15, 18, 21, 25, 29, 33). Blue/white = uptrend, gray = downtrend.
  - **WaveTrend–style wave:** fast vs slow wave; crosses mark extremes.
  - **Signals:**
    - **Green dots:** EMA 11 crosses over EMA 33 (bullish).
    - **Red cross:** EMA 5 crosses under EMA 11 (bearish).
    - **Red diamond:** bearish wavecross (fast under slow) = potential local top.
    - **Blood diamond:** red diamond **and** red cross on the **same candle** → strong bearish attention signal.
    - **Blue triangle:** EMA 5 over EMA 25 while EMA 29 &lt; EMA 33 (reversal).
    - **Yellow X:** bearish wavecross + slow wave &lt; -40 + negative money flow (warning).

There is no prominent creator named “cryptoface” in the search results; the logic is documented under **OpenCipher A** and **Market Cipher B**–style guides (e.g. Pineify). The “Blood Diamond” label is used in several scripts (e.g. Blooddiamond, Red Diamond BIAS) but the canonical definition is: **red diamond + red cross same bar**.

### What We Already Have (This Codebase)

- **`momentum_intelligence.py`** — Market Cipher–style module:
  - **Green / red diamonds:** WaveTrend-style oversold/overbought extremes + turn (wave &lt; -60 / &gt; 60, turning, with money flow).
  - **Momentum wave:** RSI + MACD–derived wave.
  - **Money flow:** MFI-style pressure.
  - **No “blood diamond” yet:** we do **not** explicitly combine “red diamond + bearish EMA cross (5 under 11) on same bar.”

### Gap & Recommendation

- **Add a “blood diamond” signal:** In `momentum_intelligence.py`, add a flag when **red_diamond** and **EMA 5 &lt; EMA 11** (red cross condition) occur on the same bar. Expose it in the `MomentumSignal` dataclass and in the bot (e.g. “BLOOD DIAMOND – strong bearish”).
- **Optional:** Align EMA lengths with OpenCipher (5, 11, 15, 18, 21, 25, 29, 33) for green dot / red cross / blue triangle replication if we want full parity.

**Conclusion:** We have done research on the Blood Diamond / OpenCipher logic. We already have diamond + wave + money flow; the one missing piece is the **blood diamond** (red diamond + red cross same bar). Adding it is a small, well-scoped change.

---

## 2. “All Available” Market-Tracking Options (Short Survey)

Beyond Blood Diamond, other TradingView-style / market-tracking ideas that are “available” and how they relate to us:

| Option | What it is | Our status |
|--------|------------|------------|
| **OpenCipher A / Market Cipher B** | EMA ribbon + WaveTrend + diamonds + crosses | We have diamonds + wave; can add blood diamond + optional full EMA set. |
| **VuManChu Cipher A** | Same family; EMA ribbons + WaveTrend | Same as above; logic is documented. |
| **Market Waves Alpha** | All-in-one combining similar signals | We’re in the same class; could add more symbols (e.g. yellow X) if we want. |
| **Unusual volume / VWAP** | Volume spikes, VWAP bands | We have `volume_anomaly.py` (volume spike detection). |
| **Order flow / footprint** | L2, tape, delta | Not in codebase; would need L2/tape data (often paid). |
| **Options flow** | Unusual options activity | Not in codebase; see “Unconventional data” below (e.g. Unusual Whales API). |

We have **not** exhaustively backtested every TradingView script, but we have:
- Researched the main “blood diamond” / Cipher family logic.
- Implemented a Cipher-style diamond + wave + money-flow module.
- Identified the exact missing piece (blood diamond = red diamond + red cross same bar).

So: **research on this class of indicators is done**; **implementation** is one step away (add blood diamond; optionally expand EMAs).

---

## 3. Recreating Bloomberg Terminal–Like Functionality

### What Bloomberg Terminal Provides

- **Data & analytics:** Real-time and historical prices, fundamentals, estimates, ownership, across asset classes.
- **News:** Bloomberg + 1,000+ sources, 5,000+ stories/day, many languages.
- **Research:** 1,500+ sell-side/independent + Bloomberg Intelligence.
- **Trading & OMS:** Execution, order management, pre/post-trade analytics.
- **Collaboration:** IB chat, 350k+ users.
- **Alternative data:** e.g. consumer transactions, foot traffic (ALTD).
- **Delivery:** Desktop app, APIs (DATA platform), enterprise feeds.

We **cannot** “recreate” the full Terminal (proprietary data, compliance, scale). We **can** recreate a **retail-scale “terminal-like” experience**: one place for data, news, screening, and alerts.

### What We Can Build (Bloomberg-*Style*)

| Bloomberg capability | Feasible replacement | Data / tools |
|---------------------|----------------------|--------------|
| Real-time / delayed quotes | Delayed or low-cost real-time | yfinance (delayed), Eulerpool free tier (delayed), TradingView Data API, Alpha Vantage |
| Historical OHLCV | Yes | yfinance, Alpha Vantage, Polygon (free tier) |
| Fundamentals & ratios | Yes | yfinance, Alpha Vantage, Finnhub |
| News + sentiment | Yes | Finnhub, Alpha Vantage News & Sentiment, Marketaux (free), GDELT (free, broad) |
| Screening / filters | Yes | Our screeners (fundamental, earnings, insider, etc.) + universe lists |
| Alerts / monitoring | Yes | Telegram bot + cron / scheduler |
| “Terminal” UI | Optional | Web dashboard (React/Next) or keep Telegram as the “terminal” |
| Alternative data | Partial | See next section (job postings, SEC, options flow, etc.) |

**Concrete “mini-Bloomberg” stack we could aim for:**

1. **Data layer**
   - Keep **yfinance** for free bulk fundamentals and history.
   - Add **one** of: **Eulerpool** (free tier 1k calls/day, delayed), **Alpha Vantage**, or **Finnhub** for more robust quotes/news/sentiment.
2. **News + sentiment**
   - **Finnhub** or **Alpha Vantage** news + sentiment API; optionally **Marketaux** for extra free news.
3. **Screening**
   - Already have: fundamental, earnings drift, insider clusters, squeeze, volume anomaly, gem scanner, winning strategy (earnings surprise 40–100%, bull regime).
   - Add: more universes (sectors, regions) and saved screens (e.g. “consumer industrials bull + earnings”).
4. **Single “command center”**
   - Telegram as today’s interface; optionally a simple web UI that shows watchlist, latest news, signals, and open positions (read-only).

**Conclusion:** Full Bloomberg replication is out of scope; **recreating the *functionality* (data + news + screening + alerts) for personal use is feasible** with free/cheap APIs and our existing backtest/signal stack.

---

## 4. Data Not Generally Used or Available — Options

These are sources that are either underused by retail or not in our codebase yet. “World at your fingertips” = APIs, official free APIs, and careful scraping where legal/ToS-compliant.

### 4.1 Free or Freemium APIs We Don’t Use Yet

| Data | Source | Notes |
|------|--------|------|
| **News + sentiment** | Finnhub, Alpha Vantage, Marketaux | Free tiers; sentiment for tickers/topics. |
| **SEC full-text search** | SEC EDGAR (last 4 years free); sec-api.io (full history, paid) | Search filings by keyword; good for event/risk signals. |
| **Options unusual activity** | Unusual Whales API, OptionData.io, Intrinio | Paid; dark pool + flow; strong for momentum/event. |
| **Economic / macro** | FRED (Federal Reserve) | Free; rates, employment, GDP — regime/context. |
| **Global trade** | UN Comtrade, WTO | Free; sector/commodity flows. |
| **Job postings** | JobSpy (Python, open source), Apify/ScrapingBee Indeed | JobSpy: free, LinkedIn/Indeed/ZipRecruiter; hiring momentum by company. |
| **Satellite / geospatial** | Sentinel Hub (free tier), Planet, ICEYE, SkyFi | Free/paid; parking lots, shipping, agriculture. |
| **App store / web** | App Annie/Data.ai (paid), SimilarWeb (paid), custom scrapes | Revenue/usage proxies; often paid. |

### 4.2 What We Already Use

- **yfinance:** price, volume, fundamentals, earnings calendar, some info.
- **SEC EDGAR (Form 4):** insider_clusters / insider_intelligence.
- **Google Trends / GitHub:** alternative_data.py (Phase 3).
- **Reddit:** sentiment_intelligence.

### 4.3 High-Value, “Not Generally Used” Additions (Prioritized)

1. **Finnhub or Alpha Vantage news + sentiment**
   - **Why:** Most retail doesn’t systematically score news by ticker; we can feed sentiment into our engine and backtests.
   - **Effort:** Low (REST, store last N headlines + score per ticker).
   - **Integration:** New small module; optional input to `run_winning_strategy` and backtest (e.g. filter or weight by sentiment).

2. **SEC full-text search (official free or sec-api.io)**
   - **Why:** Search for “layoff”, “restructuring”, “acquisition” in 10-K/10-Q/8-K; leading indicator for events.
   - **Effort:** Medium (query API, parse results, map CIK → ticker).
   - **Integration:** Event/risk overlay in screening or as a filter before taking a signal.

3. **Job postings (JobSpy or Apify)**
   - **Why:** Hiring surges by company name; already in REBUILD_STRATEGY as “job posting momentum”.
   - **Effort:** Medium (run JobSpy by company name or list of tickers → company names; track counts over time).
   - **Integration:** Alternative signal or filter in fundamental/earnings flow.

4. **FRED (macro regime)**
   - **Why:** VIX, rates, yield curve; we already have “bull regime” in the winning strategy; FRED can make regime detection data-driven.
   - **Effort:** Low (FRED API is free and simple).
   - **Integration:** Replace or augment current regime logic in `run_winning_strategy` / backtest.

5. **Unusual options / dark pool (Unusual Whales or similar)**
   - **Why:** Flow not widely used in our stack; can confirm or precede moves.
   - **Effort:** Medium; **cost:** paid API.
   - **Integration:** Optional overlay in Telegram and in backtest if we store historical flow.

6. **Satellite / geospatial (Sentinel Hub free tier or similar)**
   - **Why:** Truly alternative; retail rarely has this.
   - **Effort:** High (image pipeline, storage, interpretation).
   - **Integration:** Long-term; separate pipeline that outputs a “traffic/activity” score per company/region.

**Conclusion:** We have **not** yet integrated: news sentiment APIs, SEC full-text, job postings, FRED, or options/dark pool. These are the “not generally used or available” levers we can pull next; the table and list above are the full research set for that question.

---

## 5. Summary & Next Steps

### Research Done

- **Blood Diamond / OpenCipher:** Researched; logic is “red diamond + red cross on same bar”; we have diamonds and wave, not yet blood diamond.
- **TradingView-style options:** Surveyed Cipher family and related indicators; we’re in that class; no need to replicate every script, but we can complete the Cipher-style set (blood diamond ± full EMA set).
- **Bloomberg:** Clarified what it is; defined a realistic “mini-Bloomberg” (data + news + screening + alerts) using free/cheap APIs and current codebase.
- **Unconventional data:** Listed free/paid options (news sentiment, SEC full-text, job postings, FRED, options flow, satellite) and what we already use vs what we don’t.

### Recommended Next Steps (In Order)

1. **Add “blood diamond” to `momentum_intelligence.py`**  
   - Same-bar check: red_diamond and EMA 5 &lt; EMA 11.  
   - Expose in `MomentumSignal` and Telegram.  
   - **Effort:** Small.

2. **Add one news + sentiment API (e.g. Finnhub or Alpha Vantage)**  
   - Store recent headlines + score per ticker; optional filter/weight in strategy and backtest.  
   - **Effort:** Low.

3. **Use FRED for regime (e.g. VIX, 10Y–2Y)**  
   - Replace or augment current bull-regime logic with data-driven macro.  
   - **Effort:** Low.

4. **Design “terminal-like” command center**  
   - Either enrich Telegram (watchlist + news + signals + one “dashboard” command) or add a minimal web view.  
   - **Effort:** Medium.

5. **SEC full-text search**  
   - Add a small module (SEC or sec-api.io); keyword alerts per ticker or universe.  
   - **Effort:** Medium.

6. **Job postings (JobSpy)**  
   - Company → ticker mapping; time-series of job counts; use as filter or signal.  
   - **Effort:** Medium.

7. **Options flow / dark pool (if budget allows)**  
   - Unusual Whales or similar; overlay on top of existing signals.  
   - **Effort:** Medium; **cost:** paid.

8. **Satellite (later)**  
   - Sentinel Hub or similar; separate pipeline; integrate as an alternative score.  
   - **Effort:** High.

---

**Bottom line:** We have now done full research on (1) Blood Diamond / TradingView Cipher-style indicators, (2) what “recreating Bloomberg” means and what’s feasible, and (3) unconventional data sources and how to access them. The document above is the consolidated “world at your fingertips” map and the order in which to use it in this project.
