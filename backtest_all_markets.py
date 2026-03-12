#!/usr/bin/env python3
"""
Test the winning strategy across ALL segments: market cap, sector, country.

We previously only ran on one mixed US universe (~48 signals). This script runs
the SAME strategy (earnings beat 40-100%, hold 40d, bull regime only) on:

  - US large cap
  - US small/mid cap
  - US tech sector
  - US healthcare/biotech
  - US financials
  - US consumer / industrials
  - Canada (TSX)
  - UK (FTSE 100 style)

Then reports n_signals, median_alpha, alpha_hit_rate, win_rate per segment so we
can see which market/country/stock type the strategy is suited to.

Run: ./venv/bin/python backtest_all_markets.py
"""

import json
import logging
import os
import sys
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from backtest_engine import (
    BacktestConfig,
    fetch_and_cache_prices,
    load_earnings_history,
    run_backtest,
)

# Same strategy everywhere
WINNING_CFG = BacktestConfig(
    name="earn_h40_surp40_100_bullTrue",
    hold_days=40,
    min_surprise_pct=40,
    max_surprise_pct=100,
    require_bull_regime=True,
    signal_type="earnings",
)

# ---------------------------------------------------------------------------
# Segment universes (market cap, sector, country)
# ---------------------------------------------------------------------------

SEGMENTS: Dict[str, Dict[str, Any]] = {
    "US_large_cap": {
        "description": "US mega/large cap",
        "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "BRK-B",
            "JPM", "V", "MA", "UNH", "JNJ", "PG", "HD", "DIS", "XOM", "CVX",
            "PEP", "KO", "WMT", "MCD", "NKE", "ABBV", "MRK", "LLY", "AVGO",
            "ORCL", "CRM", "ADBE", "CSCO", "ACN", "AMD", "INTC", "QCOM", "TXN",
            "IBM", "NOW", "INTU", "AMAT", "LRCX", "MU", "ADI", "KLAC",
        ],
    },
    "US_small_mid_cap": {
        "description": "US small/mid cap growth & speculative",
        "tickers": [
            "CRWD", "DDOG", "NET", "ZS", "MDB", "HUBS", "DOCN", "S", "GTLB", "IOT",
            "BRZE", "DT", "CFLT", "PD", "SOFI", "HOOD", "AFRM", "UPST", "LMND", "LC", "NU",
            "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI", "FUBO", "PLUG", "CLOV", "LCID", "RIVN",
            "ENPH", "FSLR", "RUN", "COIN", "RBLX", "NKTR", "MRNA", "BNTX",
            "STRL", "ATKR", "UFPI", "JOBY", "ACHR", "RGTI", "QUBT", "DNA", "EDIT",
            "BFLY", "NNOX", "OUST", "INVZ", "STEM", "ARRY",
        ],
    },
    "US_tech": {
        "description": "US technology sector",
        "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "CRM", "ORCL", "ADBE",
            "CSCO", "ACN", "AMD", "INTC", "QCOM", "TXN", "AMAT", "LRCX", "MU", "KLAC",
            "CRWD", "DDOG", "NET", "ZS", "MDB", "SNOW", "PANW", "FTNT", "WDAY", "NOW",
            "INTU", "SHOP", "SQ", "PYPL", "COIN", "RBLX", "U", "GTLB", "IOT", "DOCN", "S",
        ],
    },
    "US_healthcare_biotech": {
        "description": "US healthcare & biotech",
        "tickers": [
            "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
            "AMGN", "GILD", "REGN", "VRTX", "BIIB", "MRNA", "BNTX", "ILMN",
            "TGTX", "KPTI", "PTCT", "RARE", "BMRN", "ALNY", "SRPT", "NBIX",
            "EXAS", "HALO", "PCVX", "LEGN", "BEAM", "CRSP", "NTLA", "EDIT", "DNA",
            "BFLY", "NNOX", "HOLX", "DXCM", "IDXX", "MTD", "IQV",
        ],
    },
    "US_financials": {
        "description": "US financials",
        "tickers": [
            "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "BLK", "AXP", "V", "MA",
            "SOFI", "HOOD", "AFRM", "UPST", "LC", "NU", "PYPL", "COIN",
            "AON", "MMC", "ICE", "CME", "CBOE", "NDAQ", "FIS", "GPN", "ADP",
        ],
    },
    "US_consumer_industrials": {
        "description": "US consumer & industrials",
        "tickers": [
            "WMT", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "COST", "DG",
            "CELH", "CAVA", "ELF", "ONON", "CROX", "SHAK", "BROS", "DKS",
            "AXON", "BLDR", "GNRC", "CAT", "DE", "LMT", "RTX", "HII", "GD",
            "STRL", "ATKR", "UFPI", "FAST", "CARR", "OTIS", "JCI",
        ],
    },
    "Canada": {
        "description": "Canada (TSX / US-listed Canadian)",
        "tickers": [
            "SHOP", "BMO", "RY", "TD", "BNS", "CM", "ENB", "TRP", "SU", "CNQ",
            "CP", "CNR", "AC", "WCN", "AQN", "BAM", "BB", "CSU", "OTEX",
            "SHOP.TO", "BMO.TO", "RY.TO", "TD.TO", "ENB.TO", "TRP.TO", "CP.TO", "CNR.TO",
        ],
    },
    "UK": {
        "description": "UK (FTSE 100 style, London .L)",
        "tickers": [
            "SHEL.L", "HSBA.L", "ULVR.L", "AZN.L", "GSK.L", "DGE.L", "RIO.L", "BP.L",
            "VOD.L", "TSCO.L", "REL.L", "LLOY.L", "NG.L", "BARC.L", "SAN.L", "ABF.L",
            "AAL.L", "EXPN.L", "STAN.L", "CRDA.L", "KGF.L", "SMIN.L", "ANTO.L",
        ],
    },
}


def run_segment(segment_id: str, tickers: List[str], days: int = 756) -> Dict[str, Any]:
    """Run winning strategy on one segment. Returns metrics dict."""
    tickers = list(dict.fromkeys(t.upper() for t in tickers))
    try:
        data, spy = fetch_and_cache_prices(tickers, days=days)
        if len(data) < 10:
            return {"segment_id": segment_id, "n_tickers": len(data), "error": "too_few_tickers", "n_signals": 0}
        earn = load_earnings_history(list(data.keys()))
        if len(earn) < 5:
            return {"segment_id": segment_id, "n_tickers": len(data), "error": "too_few_earnings", "n_signals": 0}
        res, df = run_backtest(data, spy, earn, WINNING_CFG)
        return {
            "segment_id": segment_id,
            "n_tickers": len(data),
            "n_earnings_tickers": len(earn),
            "n_signals": res.n_signals,
            "median_alpha_pct": round(res.median_alpha_pct, 3),
            "mean_alpha_pct": round(res.mean_alpha_pct, 3),
            "alpha_hit_rate_pct": round(res.alpha_hit_rate_pct, 2),
            "win_rate_pct": round(res.win_rate_pct, 2),
            "first_half_median_alpha": round(res.first_half_median_alpha, 3),
            "second_half_median_alpha": round(res.second_half_median_alpha, 3),
            "oos_median_alpha": round(res.oos_median_alpha, 3),
            "oos_n": res.oos_n,
            "passed": res.passed,
        }
    except Exception as e:
        return {"segment_id": segment_id, "error": str(e), "n_signals": 0}


def main():
    logger.info("Testing winning strategy (earnings 40-100%%, hold 40d, bull only) across ALL segments.")
    logger.info("")

    results = []
    for segment_id, meta in SEGMENTS.items():
        tickers = meta["tickers"]
        desc = meta["description"]
        logger.info("Segment: %s (%s) — %d tickers", segment_id, desc, len(tickers))
        out = run_segment(segment_id, tickers)
        out["description"] = desc
        results.append(out)
        if "error" in out:
            logger.info("  -> %s (n_signals=%s)", out["error"], out.get("n_signals", 0))
        else:
            logger.info("  -> n_signals=%d  median_alpha=%.2f%%  alpha_hit=%.1f%%  win_rate=%.1f%%  passed=%s",
                        out["n_signals"], out["median_alpha_pct"], out["alpha_hit_rate_pct"],
                        out["win_rate_pct"], out["passed"])
        logger.info("")

    # Summary table
    logger.info("=" * 80)
    logger.info("  SUMMARY BY SEGMENT")
    logger.info("=" * 80)
    logger.info("%-25s %6s %10s %10s %10s %8s", "Segment", "N_sig", "Med_alpha%", "Alpha_hit%", "Win_rate%", "Passed")
    logger.info("-" * 80)
    for r in results:
        if r.get("n_signals", 0) == 0:
            logger.info("%-25s %6s %10s %10s %10s %8s", r["segment_id"], "-", "-", "-", "-", "-")
        else:
            logger.info("%-25s %6d %+9.2f%% %9.1f%% %9.1f%% %8s",
                        r["segment_id"], r["n_signals"], r["median_alpha_pct"],
                        r["alpha_hit_rate_pct"], r["win_rate_pct"], str(r["passed"]))
    logger.info("=" * 80)

    # Best segment(s) — only among segments with enough signals
    with_signals = [r for r in results if r.get("n_signals", 0) >= 5]
    if with_signals:
        by_alpha = sorted(with_signals, key=lambda x: x.get("median_alpha_pct", -999), reverse=True)
        by_hit = sorted(with_signals, key=lambda x: x.get("alpha_hit_rate_pct", -999), reverse=True)
        logger.info("")
        logger.info("Best by median alpha: %s (%.2f%%, n=%d)", by_alpha[0]["segment_id"], by_alpha[0]["median_alpha_pct"], by_alpha[0]["n_signals"])
        logger.info("Best by alpha hit rate: %s (%.1f%%, n=%d)", by_hit[0]["segment_id"], by_hit[0]["alpha_hit_rate_pct"], by_hit[0]["n_signals"])
    else:
        logger.info("")
        logger.info("No segment had >= 5 signals; cannot name best.")

    # Save
    out_path = os.path.join(os.path.dirname(__file__), "backtest_cache", "all_markets_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"strategy": WINNING_CFG.name, "segments": results}, f, indent=2)
    logger.info("Saved to %s", out_path)


if __name__ == "__main__":
    main()
