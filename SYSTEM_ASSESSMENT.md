# System assessment and backtesting

**Last updated:** March 2026

---

## 1. What we have

### 1.1 Signal modules

| Module | Data source | Output | Backtestable on history? |
|--------|-------------|--------|---------------------------|
| **Technical** | Yahoo Finance OHLCV | BUY/SELL/HOLD, score −4 to +4 (RSI, MACD, SMA 20/50) | **Yes** – uses price/volume only |
| **Momentum** | Yahoo Finance OHLCV | STRONG_BUY … STRONG_SELL, diamonds, MFI, wave | **Yes** – same OHLCV |
| **David** | Yahoo + small-cap screen | List of small-cap ideas (no per-ticker signal) | Partially – scan logic could be run on past universe |
| **Sentiment** | Reddit (live API / JSON) | Score, mentions, velocity | **No** – no historical Reddit series |
| **Insider** | SEC EDGAR (live API) | 8-K/Form 4 counts, edge score | **No** – would need historical EDGAR snapshots |
| **Alternative** | Google Trends, GitHub (live) | Trend score, GitHub stars | **No** – no historical Trends/GitHub series |
| **Trade tracker** | Logged trades | P&amp;L, win rate on *actual* trades | Yes – over real history you’ve logged |

So today, the only signals we can **backtest against the market** with no extra data are:

- **Technical** (RSI, MACD, MAs) – fully backtestable.
- **Momentum** – same data, so in principle backtestable if we run it on historical DataFrames (not wired into the backtest script yet).

Everything else (sentiment, insider, alternative) is **live-only** unless we add historical APIs or proxies.

### 1.2 Data flow (live bot)

```
User → Telegram → simple_trading_bot
                       ↓
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
   get_stock_data   sentiment   insider / alt_data
   (yfinance)       (Reddit)    (SEC, Trends, GitHub)
         ↓             ↓             ↓
   get_simple_signal   score       edge score
   (RSI, MACD, MAs)   velocity    reasoning
         └─────────────┼─────────────┘
                      ↓
              Combined reply + optional trade log
```

### 1.3 Config and deployment

- **Entrypoint:** `./start_simple.sh` (venv + `simple_trading_bot.py`).
- **Config:** `trading_config.json` – TELEGRAM_*, WATCHLIST, SENTIMENT_ENABLED, MOMENTUM_ENABLED, INSIDER_ENABLED, ALTERNATIVE_DATA_ENABLED, SEC_USER_AGENT.
- **Scripts:** `check_bot.sh` / `stop_bot.sh` for the running process; logs in `simple_bot.log`.

---

## 2. Backtesting against the market

### 2.1 What the backtest does

- **Input:** Ticker list (from config `WATCHLIST` or `--tickers`), history length (`--days`), hold period (`--hold`), and step between signals (`--step`).
- **Logic:** For each date (stepping every `step_days`), take only past data and run the **same technical rules** as the live bot (RSI, MACD, SMA 20/50, score thresholds). No sentiment, insider, or alternative data.
- **Signals:** BUY when score ≥ 2, SELL when score ≤ −2. Each signal is assigned a forward return over the next `hold_days` (BUY = long return, SELL = short return).
- **Output:** Counts, average return (%), and win rate (%) for BUY and SELL over the backtest window.

So we are measuring: *if the technical rules had been used in the past, how would long (BUY) and short (SELL) have performed over the chosen hold period?*

### 2.2 How to run it

From the repo root with the same venv as the bot:

```bash
# Default: use WATCHLIST from trading_config.json, ~2y history, 20-day hold, step 5 days
./venv/bin/python backtest.py

# Custom tickers and period
./venv/bin/python backtest.py --tickers AAPL MSFT GOOGL --days 365 --hold 10 --step 5

# Save all generated signals to CSV
./venv/bin/python backtest.py --tickers AAPL MSFT --days 504 --hold 20 --out backtest_signals.csv
```

**Options:**

- `--tickers` – list of symbols (default: from config).
- `--days` – history length in calendar days (default 504 ≈ 2 years).
- `--hold` – forward return window in trading days (default 20).
- `--step` – days between signal dates (default 5; larger = fewer signals, faster).
- `--out` – optional path to write signals CSV (date, ticker, signal, price, price_future, return_pct).

### 2.3 How to interpret results

- **BUY avg return &gt; 0 and win rate &gt; 50%** – technical BUY signals would have added value over the tested period for the chosen hold.
- **SELL avg return &gt; 0** – shorts (SELL signals) would have made money on average; **SELL win rate** is the share of shorts that were profitable.
- Small sample sizes (few tickers or short history) → high variance; use more tickers and longer `--days` for a more stable view.
- This is **in-sample** on the same rules; it does not prove future performance. Use it to see if the technical edge is plausible and to tune hold/step, not as a guarantee.

### 2.4 Limitations

- **Technical only.** Sentiment, insider, and alternative data are not included; they would require historical series or approximations.
- **No costs/slippage.** Real trading has fees and spread; backtest assumes you can trade at close.
- **Single hold period.** We use one fixed `hold_days`; real strategies might exit earlier or later.
- **Momentum not in backtest yet.** The script currently uses only the technical module; momentum could be added by running it on the same historical DataFrames.

---

## 3. Possible next steps

- **Add momentum to backtest:** For each historical date, run momentum on `df.iloc[:i+1]` and record STRONG_BUY / STRONG_SELL vs forward returns (same way as technical).
- **Benchmark vs buy-and-hold:** For each ticker, compute buy-and-hold return over the same window and compare signal strategy return to it.
- **Track live vs backtest:** Compare future performance of trades logged in `trade_tracker` with backtest expectations for the same signal types.
