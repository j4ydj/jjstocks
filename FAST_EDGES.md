# Fast Edges — Short-Term, High-Volume Angles

**You said:** Not low-and-slow. Find **fast edges**, **high volume**, **short-term**. The longer-term view is the original (earnings + 40d hold). The short-term is where we uncover gold.

This doc lists **free** data sources and angles that can generate or filter **short-term** signals. All from [public-apis](https://github.com/public-apis/public-apis) or official APIs; no paid subscriptions required.

---

## 1. Prediction Markets (Free APIs)

**Why they’re a fast edge:** Prices aggregate informed views and often move **before** the underlying event. You can:
- Use **implied probability** as a filter (e.g. only long earnings when Polymarket “beat” odds are high).
- Trade the **underlying stock** before resolution when you disagree with the crowd.
- Use **macro markets** (Fed, CPI) for regime/short-term bias.

**APIs (all free, read-only):**

| Source | API | Auth | What you get |
|--------|-----|------|----------------|
| **Polymarket** | [Gamma API](https://docs.polymarket.com/api-reference/introduction) `https://gamma-api.polymarket.com` | None | Events, markets, outcome prices (implied prob), volume. Categories: Politics, Sports, Crypto, **Business** (some stock/earnings). |
| **Kalshi** | REST v2 `https://api.elections.kalshi.com/trade-api/v2` | None for market data | Orderbook, prices, events. |
| **PolyRouter** | Unified API (Polymarket + Kalshi + others) | Free tier, API key | Single interface for multiple prediction markets. |

**Implementation:** `prediction_markets.py` — fetches Polymarket active events, parses Yes/No prices → implied probability. Filter by title/slug for "earnings", "beat", "stock", "fed", etc., and use as a **short-term** signal or filter.

**Value:** When Polymarket has "Will X beat earnings?" at 70% and we have a strong earnings surprise signal, that’s confirmation. When it’s 30% and we’re bullish, that’s a potential mispricing to trade before the event.

**Where the edge is (short-term):**
- **Macro first:** Fed/CPI/employment markets often have high volume and move 24–48h before headlines. Use implied prob as regime (e.g. “cut in March” 90% → risk-on bias for growth names).
- **Earnings when listed:** Few ticker-specific “beat earnings” markets exist at any time; when they do, 60%+ Yes with our earnings surprise = confirmation; &lt;40% with our signal = possible mispricing.
- **Cross-asset:** Crypto/BTC markets on Polymarket can lead equity risk sentiment; optional filter for “risk-on” before loading growth longs.

---

## 2. Reddit / WSB Sentiment (Free)

**Why it’s fast:** Retail buzz often leads price by 24–48 hours. High mention volume + velocity = **short-term** momentum candidate.

**APIs from public-apis / web:**

| Source | Endpoint / Notes | Auth | Use |
|--------|-------------------|------|-----|
| **nbshare** | `https://dashboard.nbshare.io/apps/reddit/api/` | No (or free) | WSB trending tickers, mention counts, sentiment. |
| **ApeWisdom** | [apewisdom.io/api](https://apewisdom.io/api/) | API key (free tier) | Multi-subreddit (WSB, stocks, investing), rankings, mentions, 24h change. |
| **Reddit JSON** | `https://www.reddit.com/r/{sub}/search.json?q={ticker}` | No (User-Agent) | Already used in `sentiment_intelligence.py`; rate-limited but free. |

**What we have:** `sentiment_intelligence.py` uses Reddit JSON (and PRAW if configured). For a **fast** edge, add optional **nbshare** or **ApeWisdom** trending-tickers endpoint: get top-mentioned tickers in the last 24h and use as a **short-term** watchlist or filter (only take earnings signals when ticker is also in top WSB buzz).

---

## 3. Volume Spike (Already in Codebase)

**Module:** `volume_anomaly.py`  
**Edge:** Unusual volume + OBV breakout + price/volume agreement = **short-term** accumulation before news.  
**Data:** yfinance (free).  
**Use:** Run `scan_volume_universe(tickers)` for a **fast** list of names with 2x+ volume and accumulation score. Combine with earnings or sentiment: only take earnings longs when volume is also spiking (or use volume scan as the primary short-term screen).

**Also:** `squeeze_detector.py` — high short interest + volume surge + price up = short squeeze candidate (again short-term, high volatility).

---

## 4. News + Sentiment (Free Tiers from public-apis)

**From [public-apis Finance](https://github.com/public-apis/public-apis#finance):**

| API | Description | Auth | Short-term value |
|-----|-------------|------|-------------------|
| **MarketAux** | Live stock market news, tagged tickers, sentiment | apiKey | Headline sentiment per ticker → fast filter or trigger. |
| **Finnhub** | Real-time APIs, news, sentiment | apiKey | News + sentiment for tickers; free tier. |
| **Alpha Vantage** | News, fundamentals | apiKey | News sentiment; free tier 5 req/min. |
| **WallstreetBets** (nbshare) | WSB comments sentiment | No | Same as §2; trending + sentiment. |

**Use:** Add an optional “news sentiment” filter: only take **short-term** longs when recent headline sentiment is positive (or not highly negative). Complements prediction markets and WSB.

---

## 5. How to Use: Short-Term vs Long-Term

| Layer | Timeframe | Data | Role |
|-------|-----------|------|------|
| **Long-term (existing)** | 40d hold | Earnings surprise, bull regime | Core strategy from `run_winning_strategy.py`. |
| **Fast filter 1** | Pre-event | Prediction markets (Polymarket) | Only take earnings longs when “beat” odds are above a threshold, or trade mispricings before resolution. |
| **Fast filter 2** | 24–48h | WSB / Reddit buzz | Only take signals when ticker is in top N trending or mention velocity is high. |
| **Fast filter 3** | 1–5d | Volume spike | Only take signals when `volume_anomaly` says accumulation or spike. |
| **Fast scan** | Daily | Volume + sentiment + (optional) prediction | Standalone **short-term** scan: high volume + high buzz + (optional) high Polymarket “yes” → watchlist or short-term longs. Run: `python fast_scan.py` or `python fast_scan.py --polymarket`. |

---

## 6. Implementation Status

| Component | Status | File / Note |
|-----------|--------|-------------|
| Polymarket reader | Done | `prediction_markets.py` — active events, implied prob, filter by slug/title. |
| Volume spike | Done | `volume_anomaly.py`, `squeeze_detector.py`. |
| Reddit sentiment | Done | `sentiment_intelligence.py` (JSON + optional PRAW). |
| WSB trending (nbshare/ApeWisdom) | Doc only | Add optional client in sentiment or new `wsb_buzz.py` for trending tickers. |
| News sentiment (MarketAux/Finnhub) | Doc only | Optional module later; free tier. |
| Short-term scan script | Done | `fast_scan.py` — volume scan + optional `--polymarket` and `--sentiment`; outputs top volume names and Polymarket tradeable markets. |

---

## 7. Legal / Fair Use

- **Polymarket / Kalshi:** Public read-only APIs; no auth for market data. Use within rate limits.
- **Reddit:** User-Agent required; respect rate limits; no scraping that violates ToS.
- **nbshare / ApeWisdom:** Use per their terms; free tiers are typically non-commercial or limited.
- **News APIs:** Use within free tier and attribution rules.

---

**Bottom line:** Prediction markets give you **implied probabilities** for events (earnings, Fed, etc.) — a fast, high-information signal. WSB/sentiment and volume spike are **fast** retail/institutional footprints. Combining them with your existing long-term earnings strategy gives you **short-term** filters and a path to “fast edges” without paying for data.
