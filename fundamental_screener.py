#!/usr/bin/env python3
"""
FUNDAMENTAL SCREENER
====================
EDGE: Find growing small/mid-cap companies trading at reasonable valuations.
DATA: yfinance .info (free, no API key).
WHY:  Big funds can't touch sub-$10B companies. We find them before institutions arrive.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "ENABLED": True,
    "MIN_MARKET_CAP": 200_000_000,    # $200M
    "MAX_MARKET_CAP": 10_000_000_000, # $10B
    "MIN_REVENUE_GROWTH": 0.15,       # 15% YoY
    "MAX_EV_SALES": 10,
    "MIN_GROSS_MARGIN": 0.30,
}


@dataclass
class FundamentalSignal:
    ticker: str
    score: float           # 0-100
    market_cap: float
    revenue_growth: Optional[float]
    ev_to_sales: Optional[float]
    gross_margin: Optional[float]
    free_cash_flow: Optional[float]
    profit_margin: Optional[float]
    reasons: List[str] = field(default_factory=list)


def _safe(info: dict, key: str) -> Optional[float]:
    v = info.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def screen_stock(ticker: str, config: dict = None) -> Optional[FundamentalSignal]:
    """Score a single stock on fundamental quality. Returns None if data unavailable."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if not cfg.get("ENABLED", True):
        return None

    try:
        info = yf.Ticker(ticker).info
        if not info or info.get("quoteType") not in ("EQUITY", None):
            return None
    except Exception as e:
        logger.debug("yfinance info failed for %s: %s", ticker, e)
        return None

    mcap = _safe(info, "marketCap")
    if mcap is None:
        return None

    rev_growth = _safe(info, "revenueGrowth")
    ev_sales = _safe(info, "enterpriseToRevenue")
    gross_margin = _safe(info, "grossMargins")
    fcf = _safe(info, "freeCashflow")
    profit_margin = _safe(info, "profitMargins")

    score = 0.0
    reasons = []

    # --- Market cap: prefer small/mid ---
    min_mc, max_mc = cfg["MIN_MARKET_CAP"], cfg["MAX_MARKET_CAP"]
    if mcap < min_mc or mcap > max_mc:
        # Outside target range — still score it but penalise
        if mcap < min_mc:
            return None  # too small, likely illiquid
        score -= 10
        reasons.append(f"Large-cap ${mcap/1e9:.1f}B (prefer <${max_mc/1e9:.0f}B)")
    else:
        score += 15
        reasons.append(f"Small/mid-cap ${mcap/1e9:.1f}B")

    # --- Revenue growth ---
    if rev_growth is not None:
        if rev_growth >= 0.50:
            score += 30
            reasons.append(f"Exceptional revenue growth {rev_growth:.0%}")
        elif rev_growth >= 0.25:
            score += 25
            reasons.append(f"Strong revenue growth {rev_growth:.0%}")
        elif rev_growth >= cfg["MIN_REVENUE_GROWTH"]:
            score += 15
            reasons.append(f"Solid revenue growth {rev_growth:.0%}")
        elif rev_growth >= 0:
            score += 5
            reasons.append(f"Modest growth {rev_growth:.0%}")
        else:
            score -= 10
            reasons.append(f"Revenue declining {rev_growth:.0%}")

    # --- Valuation (EV/Sales) ---
    if ev_sales is not None and ev_sales > 0:
        if ev_sales <= 3:
            score += 25
            reasons.append(f"Cheap valuation EV/S={ev_sales:.1f}")
        elif ev_sales <= 6:
            score += 15
            reasons.append(f"Reasonable valuation EV/S={ev_sales:.1f}")
        elif ev_sales <= cfg["MAX_EV_SALES"]:
            score += 5
            reasons.append(f"Moderate valuation EV/S={ev_sales:.1f}")
        else:
            score -= 10
            reasons.append(f"Expensive EV/S={ev_sales:.1f}")

    # --- Gross margin ---
    if gross_margin is not None:
        if gross_margin >= 0.60:
            score += 15
            reasons.append(f"High-quality margins {gross_margin:.0%}")
        elif gross_margin >= cfg["MIN_GROSS_MARGIN"]:
            score += 10
            reasons.append(f"Healthy margins {gross_margin:.0%}")
        else:
            score -= 5
            reasons.append(f"Thin margins {gross_margin:.0%}")

    # --- Free cash flow ---
    if fcf is not None:
        if fcf > 0:
            score += 10
            reasons.append("FCF positive")
        else:
            score -= 5
            reasons.append("FCF negative (cash burn)")

    # --- Profitability ---
    if profit_margin is not None:
        if profit_margin > 0.15:
            score += 5
            reasons.append(f"Profitable ({profit_margin:.0%} margin)")
        elif profit_margin > 0:
            score += 2

    score = max(0, min(100, score))

    return FundamentalSignal(
        ticker=ticker,
        score=score,
        market_cap=mcap,
        revenue_growth=rev_growth,
        ev_to_sales=ev_sales,
        gross_margin=gross_margin,
        free_cash_flow=fcf,
        profit_margin=profit_margin,
        reasons=reasons,
    )


def screen_universe(tickers: List[str], config: dict = None,
                    min_score: float = 40) -> List[FundamentalSignal]:
    """Screen a list of tickers, return those passing min_score, sorted best-first."""
    results = []
    for tk in tickers:
        sig = screen_stock(tk, config)
        if sig and sig.score >= min_score:
            results.append(sig)
        time.sleep(0.15)  # rate-limit yfinance
    results.sort(key=lambda s: s.score, reverse=True)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sample = ["SOFI", "CRWD", "HUBS", "CELH", "CAVA", "ELF", "ONON", "AAPL", "RKLB", "SOUN"]
    for s in screen_universe(sample, min_score=0):
        print(f"  {s.ticker:6s}  score={s.score:5.1f}  mcap=${s.market_cap/1e9:.1f}B  "
              f"growth={s.revenue_growth or 0:.0%}  EV/S={s.ev_to_sales or 0:.1f}  "
              f"| {'; '.join(s.reasons[:3])}")
