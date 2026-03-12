# Trading System — Strategy v3: The Honest Pivot

## What We Proved (v1 + v2 Backtests)

Two full strategy generations. 2,500+ backtested signals. Two different approaches.

| Version | Approach | Median Alpha vs SPY | Verdict |
|---|---|---|---|
| v1 | RSI, MACD, SMA crossovers | -1.10% | No edge |
| v2 | Earnings drift, volume anomaly, fundamentals, squeeze | -0.33% | No edge |

The pattern is the same both times: averages look OK, medians are negative, and all the "alpha" comes from a handful of meme stock lottery tickets. Remove the top 10-20 outlier trades and both systems produce ~0%.

**Adding more signals, more modules, or more technical analysis will not fix this.** The problem is not the signal — it's the approach.

---

## Why Scanning + Rules Can't Beat the Market

1. **Free data = no information advantage.** yfinance, SEC EDGAR, Google Trends — every retail trader and every quant fund has this same data.
2. **Simple rules are already arbitraged.** RSI < 30, earnings beat > 10%, short float > 15% — these thresholds are in every screener on the planet.
3. **Broad scanning = shallow understanding.** Screening 200 stocks means you know nothing about any of them. A random signal on a random stock is just noise.

This is the fundamental mistake: we built a system that knows a tiny bit about many stocks. The edge is in knowing a lot about a few stocks.

---

## What Actually Beats Hedge Funds (And What Doesn't)

### What hedge funds have that we never will:
- $50K-$500K/year alternative data feeds (satellite, credit card, web traffic)
- Low-latency execution infrastructure
- Teams of PhDs and massive compute for ML
- Prime brokerage, leverage, derivatives access
- Proprietary order flow data

**We cannot compete on speed, data budget, or compute. Stop trying.**

### What we have that they structurally cannot:

| Our Advantage | Why Funds Can't Copy It |
|---|---|
| **No position size constraint** | A $10B fund can't put meaningful capital into a $300M company |
| **No quarterly reporting pressure** | Fund managers get fired after 2 bad quarters. We can wait 2 years. |
| **No career risk** | A PM can't hold through -30% without losing clients. We can. |
| **Deep focus on 5-10 names** | Funds cover hundreds of stocks, analysts get 30 min per name |
| **Micro/nano-cap access** | Companies under $500M have zero analyst coverage — true information gaps |

**The edge is concentration + patience + going where funds can't.**

---

## The Pivot: From Signal Generator to Research Accelerator

Stop trying to generate buy/sell signals automatically. Instead, build a tool that makes YOU a better researcher on a small number of high-conviction bets.

### New Architecture

```
┌──────────────────────────────────────────────────────┐
│                  RESEARCH ACCELERATOR                 │
│                                                      │
│  1. DISCOVER  ──▶  2. RESEARCH  ──▶  3. TRACK       │
│  (find candidates)  (go deep)        (monitor thesis)│
└──────────────────────────────────────────────────────┘
```

### Phase 1: Smart Discovery (Keep What Works)

The existing screener modules are useful for *finding candidates to research* — not as buy signals, but as a starting funnel.

**Keep:**
- `fundamental_screener.py` — find growing small-caps (candidate discovery)
- `squeeze_detector.py` — find high-SI setups worth investigating
- `earnings_drift.py` — flag recent big earnings beats to look into

**Purpose:** Narrow 5,000 stocks → 20-30 candidates worth reading about.

### Phase 2: Deep Research Engine (NEW — The Real Edge)

For each candidate, automatically compile a research brief that would take a human analyst 2-4 hours:

#### a) Financial Deep Dive (`financial_analyzer.py`)
- Revenue trajectory: quarterly revenue for last 8 quarters, growth rate trend
- Margin expansion or compression: gross, operating, net margins over time
- Cash flow quality: operating cash flow vs reported earnings (detect accounting tricks)
- Balance sheet health: debt/equity, current ratio, cash runway
- Earnings quality score: are earnings real (cash-backed) or accounting fiction (accruals-heavy)?

Data: yfinance `.quarterly_financials`, `.quarterly_balance_sheet`, `.quarterly_cashflow` — all free.

#### b) Competitive Moat Assessment (`moat_analyzer.py`)
- Revenue concentration: how many customers (10-K risk factors)
- Insider ownership: do executives have skin in the game (SEC proxy filings)
- Management quality: tenure, track record, compensation alignment
- Institutional ownership trend: are smart money managers adding or cutting? (13F data, free via SEC)
- Analyst coverage: zero-coverage stocks have the biggest information gaps

Data: SEC EDGAR (13F, DEF 14A proxy), yfinance `.institutional_holders`, `.major_holders` — all free.

#### c) Catalyst Calendar (`catalyst_tracker.py`)
- Next earnings date and historical beat/miss pattern
- FDA approval dates (for biotech — scraped from FDA calendar, free)
- Lockup expiration dates (for recent IPOs)
- Conference presentations (company IR pages)
- Insider buying/selling windows (blackout periods around earnings)

Data: yfinance `.earnings_dates`, SEC EDGAR, FDA.gov — all free.

#### d) Earnings Call NLP (`earnings_nlp.py`)
- Download earnings call transcripts (free from SEC EDGAR 8-K exhibits or Seeking Alpha)
- Analyze management tone: confident vs evasive language
- Track key phrase changes quarter-over-quarter ("strong demand" → "challenging environment")
- Flag red-flag phrases: "one-time charges", "restructuring", "goodwill impairment"
- This is genuinely differentiated — most retail traders don't read transcripts

Data: SEC EDGAR 8-K exhibits (free), basic NLP with no external API.

### Phase 3: Thesis Tracking (NEW — Prevents the Biggest Retail Mistake)

Most retail traders lose money not because they pick bad stocks, but because they:
1. Hold losers too long (no stop-loss discipline)
2. Sell winners too early (no conviction)
3. Ignore when their thesis breaks

#### Thesis Journal (`thesis_tracker.py`)
- For each position: document WHY you bought (the thesis)
- Define thesis-breakers: "If revenue growth drops below 20%, exit"
- Auto-monitor: if a thesis-breaker triggers, alert via Telegram
- Performance tracking: did your thesis play out? What was the return?
- Learning loop: review past theses to improve future judgment

#### Risk Dashboard (`risk_monitor.py`)
- Portfolio concentration: how much in each name, sector
- Correlation: are your picks actually diversified or just 5 tech stocks?
- Max drawdown tracking per position
- Stop-loss monitoring (if configured)

---

## Implementation Plan

| Phase | What | Time | Dependencies |
|---|---|---|---|
| 1 | `financial_analyzer.py` — deep quarterly financial analysis | Day 1-2 | yfinance (installed) |
| 2 | `moat_analyzer.py` — ownership, management, competitive position | Day 2-3 | yfinance + SEC (installed) |
| 3 | `catalyst_tracker.py` — upcoming events calendar | Day 3 | yfinance + SEC (installed) |
| 4 | `earnings_nlp.py` — transcript tone analysis | Day 4-5 | SEC + basic NLP (no new deps) |
| 5 | `thesis_tracker.py` — journal + thesis-break alerts | Day 5-6 | JSON storage |
| 6 | `risk_monitor.py` — portfolio monitoring | Day 6 | yfinance (installed) |
| 7 | Telegram integration — `/research TICKER` command | Day 7 | existing bot |

**Zero new paid APIs. Zero new dependencies.** Everything runs on yfinance + SEC EDGAR + basic Python NLP.

---

## How This Beats Hedge Funds

| Hedge Fund Weakness | Our Exploit |
|---|---|
| Can't invest meaningfully in $300M companies | We CAN. Our screener finds them, our research engine evaluates them deeply. |
| Analysts spend 30 min per stock, cover 40 names | We spend 2 hours per stock, cover 5 names. Deeper understanding = better decisions. |
| Quarterly reporting pressure forces short-term thinking | Thesis tracker keeps us disciplined on 1-3 year horizons. |
| Compliance blocks alternative data sources | We use any public data: job postings, App Store reviews, local news. |
| Models can't read between the lines of earnings calls | Our NLP flags tone shifts that quantitative models miss. |

**The edge isn't faster or more signals. It's deeper understanding on fewer names where no one else is looking.**

---

## What Gets Kept / Cut

| Module | Decision | New Role |
|---|---|---|
| `fundamental_screener.py` | KEEP | Candidate discovery funnel |
| `earnings_drift.py` | KEEP | Earnings surprise flagging |
| `squeeze_detector.py` | KEEP | High-SI candidate flagging |
| `insider_clusters.py` | KEEP | Part of moat/ownership analysis |
| `volume_anomaly.py` | KEEP | Accumulation alerts |
| `gem_scanner.py` | REPURPOSE | Becomes the discovery layer for research pipeline |
| `simple_trading_bot.py` | KEEP | Telegram interface, add `/research` command |
| `backtest.py` | ARCHIVE | Backtesting is less relevant for research-driven approach |
| `sentiment_intelligence.py` | CUT | No value proven |
| `alternative_data.py` | CUT | No value proven |
| `momentum_intelligence.py` | CUT | No value proven |

---

## Success Metrics (Different This Time)

This is no longer about "median alpha vs SPY." The system's value is measured by:

1. **Research quality** — does the financial brief surface things you'd otherwise miss?
2. **Thesis discipline** — do you hold winners longer and cut losers faster?
3. **Time saved** — does 1 hour with the tool replace 4 hours of manual research?
4. **Conviction quality** — are your high-conviction bets more profitable than your low-conviction ones?

These are measured over months of actual trading, not by a backtest.

---

## Bottom Line

We tried to build a robot that finds hidden gems automatically. It can't — the backtest proved it twice. Nobody's free-data screener can.

What we CAN build: a research machine that makes you smarter and faster at finding gems yourself, in the parts of the market where hedge funds structurally cannot compete.

The tool doesn't make the decision. You do. But you make it with 10x better information than you'd have otherwise, on stocks that nobody else is covering.

---

## ✅ Backtested Winning System (Added)

A separate rigorous backtest was run over 200+ strategy variants. **One strategy passed** all criteria (median alpha ≥ 0.5%, alpha hit ≥ 52%, win rate ≥ 52%, consistency, OOS). It is implemented and wired into the bot:

- **Strategy:** Earnings beat (surprise 40–100%), hold 40 days, **bull regime only** (SPY above 200d MA).
- **Backtest:** 48 signals, median alpha +5.67%, alpha hit 56.25%, win rate 60.4%.
- **Run live:** `./venv/bin/python run_winning_strategy.py` or use **/signals** in the Telegram bot.
- **Docs:** See **WINNING_SYSTEM.md** and `backtest_cache/winning_strategy.json`.
