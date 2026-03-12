# Path Less Travelled — Free, Legal Edges

**No paid data. No subscriptions. Legal only.** These are underused or structurally neglected edges that stay within the law.

---

## 1. Philosophy

- **Crowded data** (earnings surprise, RSI, same-day news) is arbitraged. The edge is in **data everyone has but almost no one uses well**, or **structure the crowd ignores**.
- **Free and legal:** SEC EDGAR, Wikipedia, public index reconstitution dates, lockup disclosures. We use them with proper rate limits and User-Agent; no insider info, no hacking.
- **You said:** find a way to win; ignore your direction if needed; pushing morality slightly is fine as long as we stay legal. So we stay **strictly legal** and focus on **unconventional use of public data**.

---

## 2. Free Edges Implemented or Documented

### 2.1 SEC filing risk filter (implemented)

- **What:** Scan the **latest 10-K or 10-Q** (full text) for risk phrases: "going concern", "substantial doubt", "material weakness", "restructuring", "layoff", "bankruptcy", "default".
- **Source:** SEC EDGAR, 100% free. `data.sec.gov` submissions + fetch primary document from `sec.gov/Archives/edgar/...`. User-Agent required; 10 requests/second.
- **Use:** Only take **long** earnings signals when the ticker is **clean** (no recent risk language). Avoid names that just told the world they’re in trouble.
- **Why it’s underused:** Most screeners don’t parse 10-K/10-Q text. We’re not paying for Refinitiv; we’re using the same filings the SEC gives everyone.

### 2.2 Wikipedia pageview momentum (implemented)

- **What:** Track **Wikipedia page views** for the company (or ticker) over the last 7–30 days. Rising views = rising attention; can lead or confirm retail interest.
- **Source:** Wikimedia Pageviews API, free. Requires a descriptive User-Agent.
- **Use:** Filter or score: only take signals when pageviews are rising (or use as a ranking). Completely public, no paywall.
- **Why it’s underused:** Quants use price/volume; retail uses social. Almost no one systematically uses Wikipedia traffic as a signal.

### 2.3 Russell reconstitution (documented, strategy only)

- **What:** Russell 2000 reconstitution is the **fourth Friday of June** (and from 2026, also second Friday of December). Forced indexer buying in the last days of June.
- **Source:** Dates are public (FTSE Russell, CME). No API cost.
- **Use:** Long small caps / IWM in the **last week of June**; or trade adds/deletes if you have the list (published by FTSE Russell). Pure calendar + public info.
- **Why it’s underused:** Many retail traders don’t trade on index mechanics; it’s a known but still exploitable seasonality.

### 2.4 Lockup expiry (documented)

- **What:** After IPO, insiders are locked up (often **180 days**). Lockup terms are in the **S-1/prospectus** on EDGAR. When lockup expires, supply can spike and price often dips, then sometimes mean-reverts.
- **Source:** SEC EDGAR, free. Parse S-1 for lockup language; IPO date is public.
- **Use:** Avoid buying **just before** lockup expiry; or consider buying the **dip** after expiry if the thesis is still intact. All from public filings.

### 2.5 13F timing (documented)

- **What:** Hedge funds file **13F** (holdings) quarterly. Filings are **public** and free. When a known fund shows a new position, retail can follow with a delay.
- **Source:** SEC EDGAR, 13F filings. Free.
- **Use:** Screen for “new 13F position in last quarter” and then apply our earnings/quality filters. Not front-running; we’re using the same delayed public data.

---

## 3. What We Built

- **`sec_filing_risk.py`** — Fetches latest 10-K/10-Q for a ticker from SEC (free), scans for risk phrases, returns `clean` / `risky` or a score. Use as a filter: **only long when clean**.
- **`wikipedia_views.py`** — Fetches last 7–30 days Wikipedia pageviews for a company/ticker (free). Returns trend and optional score. Use as **momentum filter** or ranking.
- **`PATH_LESS_TRAVELLED.md`** (this file) — All of the above in one place.

---

## 4. How to Use in the Strategy

- **Earnings + SEC risk filter:** In `run_winning_strategy`, before emitting a signal, call `sec_filing_risk.is_clean(ticker)`. If `False`, **drop** the signal. Hypothesis: avoid blow-ups that just disclosed risk.
- **Earnings + Wikipedia momentum:** Optionally keep only signals where `wikipedia_views.trend(ticker)` is `up` over the last 14 days. Or rank signals by pageview growth.
- **Russell reconstitution:** Add a separate “recon” signal: in the last 5 trading days of June, go long IWM or a small-cap basket (separate from earnings strategy). No new data cost.

---

## 5. Legal Line

- **We do:** Public SEC filings, public APIs (Wikipedia, SEC), public dates (Russell, lockup from S-1). Rate limits and User-Agent as required.
- **We do not:** Insider information, unauthorized access, market manipulation, or scraping in a way that violates computer fraud laws. “Pushing morality slightly” does not mean breaking the law.

---

## 6. Master’s Take

The path less travelled is **not a single magic dataset**. It’s **using free, public data in a way most people don’t**: reading the 10-K for risk, watching Wikipedia for attention, and trading calendar/structure (Russell, lockup) instead of only price. This doc and the two modules are that path — free and legal.

---

## 7. Does It Work? — Full Analysis

We ran **`analyze_path_less_travelled.py`** on the same winning strategy (earnings 40–100%, bull, 40d) and compared:

- **Baseline (no filter)** — all signals
- **SEC clean only** — drop tickers whose *current* 10-K/10-Q has risk phrases
- **Wiki trend > 0** — keep only tickers with rising Wikipedia pageviews (current 14d)
- **Wiki top 50% by trend** — keep signals in the top half of tickers by pageview momentum
- **SEC clean + Wiki > 0** — both filters

**Caveat:** The analysis uses **current** SEC/Wiki state as a proxy (we don't have historical 10-K or pageviews per signal date). So it answers: "Would filtering to tickers that are clean today and have rising attention have improved our historical returns?"

### Results (full universe, one run)

| Variant              | n   | median_alpha% | alpha_hit% | win_rate% |
|----------------------|-----|---------------|------------|-----------|
| Baseline (no filter) | 93  | **-0.66**     | 47.3       | 53.8      |
| SEC clean only       | 92  | -0.98         | 46.7       | 54.3      |
| Wiki trend > 0       | 71  | -1.30         | 46.5       | 54.9      |
| Wiki top 50% by trend| 52  | -0.90         | 48.1       | **55.8**  |
| SEC clean + Wiki > 0 | 71  | -1.30         | 46.5       | 54.9      |

- **SEC filter:** Almost all tickers were "clean" (43/44); it dropped one signal and median alpha was slightly worse. So in this run the SEC filter **did not improve** results.
- **Wikipedia:** "Wiki top 50%" had **higher win rate** (55.8% vs 53.8%) and slightly better alpha hit (48.1% vs 47.3%) but **worse median alpha** (-0.90% vs -0.66%) and fewer signals (52 vs 93).

### Recommendation

- **Default:** On this analysis run, **baseline (no SEC filter, no Wiki rank)** had the best median alpha. So it's reasonable to run with **`--no-sec-filter`** and **without** `--wiki-rank` if you care most about median alpha and signal count.
- **If you want fewer, higher win-rate signals:** Use **`--wiki-rank`** (or a "Wiki top 50%" style filter) to rank by attention; you get fewer signals and a modest win-rate bump at the cost of median alpha in this test.
- **SEC filter:** Keep it **off** unless you specifically want to avoid names with current risk language in 10-K/10-Q; in the test it didn't improve results and almost no tickers were dropped.

Re-run the analysis yourself to confirm on your universe and data:

```bash
./venv/bin/python analyze_path_less_travelled.py          # full universe
./venv/bin/python analyze_path_less_travelled.py --small  # quick (20 tickers)
./venv/bin/python analyze_path_less_travelled.py --skip-sec   # Wiki only
./venv/bin/python analyze_path_less_travelled.py --skip-wiki  # SEC only
```

So: **yes, the plumbing works**; whether the filters **improve** results depends on the run and your priority (median alpha vs win rate vs number of signals). Dropping the SEC filter and using Wiki only for optional ranking is a reasonable default after this analysis.
