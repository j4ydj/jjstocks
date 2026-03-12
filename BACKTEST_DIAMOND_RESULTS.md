# Diamond Strategy: Not Good Enough (Summary)

## What we tested

1. **Pure diamond** – Green diamond = buy, hold 20 or 40 days, with/without bull regime, stricter threshold (-70), step 7 days.  
2. **Diamond + earnings combo** – Green diamond only when there was a recent earnings beat (20% or 40% in last 60d).  
3. **Earnings + diamond filter** – Winning strategy (earnings 40–100%, bull, 40d) but only keep entries where a green diamond fired within 20 days after entry.

## Results

| Variant                         | N   | Median α | Alpha hit | Pass? |
|---------------------------------|-----|----------|-----------|-------|
| diamond_hold40_bull             | 73  | -3.75%   | 35.6%     | No    |
| diamond_hold20_bull             | 75  | -1.04%   | 44.0%     | No    |
| diamond_step7_hold40_bull       | 49  | -0.32%   | 49.0%     | No    |
| diamond_combo_surp40_hold40_bull| 5   | **+5.05%** | **60%**   | No (n&lt;30) |
| earnings_diamond (filter)       | 2   | -24%     | 0%        | No    |

- **Pure diamond:** No variant passes. Best is step7 with median α ≈ -0.32% and alpha hit 49% (below 52% bar).  
- **Diamond_combo with 40% surprise:** Strong median α (+5.05%) and 60% alpha hit but only 5 signals; engine requires n ≥ 30.  
- **Earnings + diamond filter:** Almost no overlap (0–2 signals); when we get signals they are bad.

## Conclusion

- **Diamond (Market Cipher / OpenCipher) green diamond is not good enough** as a standalone entry rule or as a filter on the winning strategy.  
- The only diamond variant with strong per-trade stats is **diamond_combo (surprise ≥ 40%)**, but it yields too few signals to pass the bar or to rely on in practice.

## What to use instead

- **Live signals:** Use the **winning strategy** only: earnings surprise 40–100%, hold 40 days, **bull regime only** (see `WINNING_SYSTEM.md` and `run_winning_strategy.py`).  
- **Diamond:** Keep as **optional context** in the bot (e.g. “green/red/blood diamond” in `/analyze`) for awareness, not as an entry condition.  
- **If you want more edge later:** Focus on more data (e.g. news sentiment, SEC, job postings) or other strategy ideas; diamond alone does not clear the bar.

## How to rerun

```bash
python3 backtest_diamond.py
```

This runs all diamond variants and reports the best by median alpha (with n ≥ 15). None currently pass.
