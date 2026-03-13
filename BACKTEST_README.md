# Backtest & Framework Choice

## Running the backtest

```bash
python backtest_edge.py [start_date] [end_date]
# Example:
python backtest_edge.py 2020-01-01 2024-01-01
```

The script uses **Backtrader** with a simplified Edge strategy (3 signals: trend, momentum, volume; conviction ≥ 2; 2:1 R:R, 2% risk, 30-day hold). It runs on a single stock (default AAPL) + SPY and prints final value, return %, and SPY buy‑and‑hold for comparison.

---

## Is this good enough, or should you use vectorbt or QuantConnect?

### Backtrader (current)

| Pros | Cons |
|------|------|
| Simple bar‑by‑bar logic, easy to match your live rules | Single‑asset or manual multi‑asset; no built‑in portfolio/vectorization |
| No cloud dependency, runs locally | Slower on large universes (loop over bars) |
| Good for sanity checks and a few names | Limited analytics; you’d add your own metrics |

**Verdict:** Good enough for **single‑name or small‑universe checks** and to confirm that entries/exits and sizing behave as intended. Not ideal for **full S&P 500 portfolio** backtests or heavy research.

---

### vectorbt

| Pros | Cons |
|------|------|
| **Vectorized**: entire history at once, very fast on 500+ tickers | Steeper learning curve (pandas/numpy style) |
| Built‑in metrics (Sharpe, drawdown, etc.) and plots | You express logic in array form, not “if bar 1 then buy” |
| Native portfolio backtesting (many symbols, weights) | Less natural for “hold 30 days then exit” without some setup |

**Verdict:** Use **vectorbt when you want speed and proper multi‑name portfolio backtests** (e.g. your full edge universe). Best if you’re comfortable with pandas/numpy and can translate your rules into vectorized conditions.

---

### QuantConnect

| Pros | Cons |
|------|------|
| Production‑grade: live paper/live trading, same code as backtest | Cloud‑only; learning curve (LEAN, C# or Python) |
| Institutional data (adjustments, corporate actions, options) | Overkill for a personal scanner that only needs daily bars |
| Realistic execution/slippage and portfolio margin | Tied to their ecosystem and data |

**Verdict:** Use **QuantConnect when you care about live/paper deployment and institutional data**, not for “is my idea sane?” backtests. For your current use case (scan → Telegram alerts, manual execution), it’s usually more than you need.

---

## Recommendation

- **Keep Backtrader** for quick, single‑name (or small universe) checks and to validate that your Edge logic and risk (2:1 R:R, 2% risk, 30‑day hold) behave as you expect.
- **Add vectorbt** when you want to backtest the **full universe** (e.g. 500 names) with proper portfolio aggregation and speed; that’s when “is this good enough?” is best answered with vectorized, multi‑name results.
- **Skip QuantConnect** unless you later move to automated execution and need their data and infrastructure.

In short: **Backtrader = good enough for logic checks and a few names; vectorbt = next step for full‑universe, portfolio-level backtests; QuantConnect = only if you need live trading and institutional data.**
