#!/usr/bin/env python3
"""
GEM SCANNER — Signal Fusion Layer
==================================
Runs all 5 modules on a stock universe and flags "hidden gems" where
2+ independent signals agree.  This is the core screening engine.

Usage:
  ./venv/bin/python gem_scanner.py                     # scan default universe
  ./venv/bin/python gem_scanner.py --tickers SOFI RKLB # scan specific tickers
"""

import argparse
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# --- Module imports (all optional, degrade gracefully) ---
try:
    from fundamental_screener import screen_stock, FundamentalSignal
    FUNDAMENTAL_OK = True
except ImportError:
    FUNDAMENTAL_OK = False

try:
    from earnings_drift import analyze_earnings, EarningsDriftSignal
    EARNINGS_OK = True
except ImportError:
    EARNINGS_OK = False

try:
    from insider_clusters import analyze_insider_cluster, InsiderClusterSignal
    INSIDER_OK = True
except ImportError:
    INSIDER_OK = False

try:
    from squeeze_detector import analyze_squeeze, SqueezeSignal
    SQUEEZE_OK = True
except ImportError:
    SQUEEZE_OK = False

try:
    from volume_anomaly import analyze_volume, VolumeSignal
    VOLUME_OK = True
except ImportError:
    VOLUME_OK = False


# Broad scan universe — small/mid/large mix across sectors
SCAN_UNIVERSE = [
    # Tech / SaaS
    "CRWD", "DDOG", "NET", "ZS", "MDB", "HUBS", "DOCN", "S", "GTLB", "IOT",
    "BRZE", "DT", "CFLT", "PD",
    # Fintech
    "SOFI", "HOOD", "AFRM", "UPST", "LMND", "LC", "NU", "PAYO",
    # Biotech / Health
    "TGTX", "KPTI", "PTCT", "RARE", "BMRN", "ALNY", "SRPT", "NBIX",
    "EXAS", "HALO", "PCVX", "LEGN", "RCKT", "BEAM", "CRSP", "NTLA",
    # Consumer
    "CELH", "CAVA", "ELF", "ONON", "CROX", "SHAK", "BROS", "DKS",
    # Industrial / Energy
    "AXON", "BLDR", "GNRC", "CLF", "AA", "MP", "FANG", "MTDR",
    # Space / Deep Tech
    "RKLB", "LUNR", "ASTS", "IONQ", "SOUN", "BBAI",
    # Speculative / high SI
    "FUBO", "PLUG", "CLOV", "LCID", "RIVN",
    # Clean energy
    "ENPH", "FSLR", "RUN",
    # Large-cap benchmarks (to verify we're finding relative edge)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
]

MIN_SIGNALS_FOR_GEM = 2
FUNDAMENTAL_THRESHOLD = 40  # score out of 100
VOLUME_THRESHOLD = 65


@dataclass
class GemResult:
    ticker: str
    gem_score: float               # combined confidence
    active_signals: List[str]      # which modules fired
    fundamental: Optional[dict] = None
    earnings: Optional[dict] = None
    insider: Optional[dict] = None
    squeeze: Optional[dict] = None
    volume: Optional[dict] = None
    reasons: List[str] = field(default_factory=list)


def scan_single(ticker: str, config: dict = None) -> GemResult:
    """Run all modules on a single ticker and return the combined result."""
    cfg = config or {}
    signals = []
    reasons = []
    gem = GemResult(ticker=ticker, gem_score=0, active_signals=[])

    # 1. Fundamentals
    if FUNDAMENTAL_OK:
        try:
            fs = screen_stock(ticker, cfg.get("FUNDAMENTAL_SCREENER"))
            if fs and fs.score >= FUNDAMENTAL_THRESHOLD:
                signals.append("FUNDAMENTAL")
                reasons.extend(fs.reasons[:2])
                gem.fundamental = {"score": fs.score, "mcap": fs.market_cap,
                                   "growth": fs.revenue_growth, "ev_sales": fs.ev_to_sales}
        except Exception as e:
            logger.debug("fundamental failed %s: %s", ticker, e)

    # 2. Earnings drift
    if EARNINGS_OK:
        try:
            es = analyze_earnings(ticker, cfg.get("EARNINGS_DRIFT"))
            if es and es.signal == "BUY":
                signals.append("EARNINGS_BEAT")
                reasons.extend(es.reasons[:2])
                gem.earnings = {"surprise_pct": es.surprise_pct, "date": es.earnings_date,
                                "confidence": es.confidence}
        except Exception as e:
            logger.debug("earnings failed %s: %s", ticker, e)

    # 3. Insider clusters
    if INSIDER_OK:
        try:
            ic = analyze_insider_cluster(ticker, cfg.get("INSIDER_CLUSTERS"))
            if ic and ic.signal == "CLUSTER_BUY":
                signals.append("INSIDER_BUY")
                reasons.extend(ic.reasons[:2])
                gem.insider = {"buyers": ic.cluster_buys, "buy_value": ic.total_buy_value,
                               "confidence": ic.confidence}
        except Exception as e:
            logger.debug("insider failed %s: %s", ticker, e)

    # 4. Squeeze setup
    if SQUEEZE_OK:
        try:
            sq = analyze_squeeze(ticker, cfg.get("SQUEEZE_DETECTOR"))
            if sq and sq.signal == "SQUEEZE_SETUP":
                signals.append("SQUEEZE")
                reasons.extend(sq.reasons[:2])
                gem.squeeze = {"score": sq.score, "short_pct": sq.short_pct_float,
                               "vol_mult": sq.volume_multiple}
        except Exception as e:
            logger.debug("squeeze failed %s: %s", ticker, e)

    # 5. Volume anomaly
    if VOLUME_OK:
        try:
            va = analyze_volume(ticker, cfg.get("VOLUME_ANOMALY"))
            if va and va.signal in ("ACCUMULATION", "SPIKE_BUY") and va.accumulation_score >= VOLUME_THRESHOLD:
                signals.append("VOLUME")
                reasons.extend(va.reasons[:2])
                gem.volume = {"score": va.accumulation_score, "vol_mult": va.volume_multiple,
                              "obv_breakout": va.obv_breakout}
        except Exception as e:
            logger.debug("volume failed %s: %s", ticker, e)

    gem.active_signals = signals
    gem.reasons = reasons
    gem.gem_score = round(len(signals) / 5 * 100, 1)  # simple: % of modules that fired
    return gem


def scan_universe(tickers: List[str] = None, config: dict = None,
                  min_signals: int = MIN_SIGNALS_FOR_GEM) -> List[GemResult]:
    """Scan the full universe and return gems (stocks with >= min_signals agreeing)."""
    tickers = tickers or SCAN_UNIVERSE
    tickers = list(dict.fromkeys(t.upper() for t in tickers))  # dedup

    logger.info("Scanning %d tickers across %d modules ...",
                len(tickers),
                sum([FUNDAMENTAL_OK, EARNINGS_OK, INSIDER_OK, SQUEEZE_OK, VOLUME_OK]))

    results = []
    for i, tk in enumerate(tickers):
        r = scan_single(tk, config)
        if len(r.active_signals) >= min_signals:
            results.append(r)
        if (i + 1) % 20 == 0:
            logger.info("  ... %d / %d tickers scanned", i + 1, len(tickers))

    results.sort(key=lambda g: (len(g.active_signals), g.gem_score), reverse=True)
    return results


def print_results(gems: List[GemResult]):
    if not gems:
        logger.info("\nNo hidden gems found (no stocks with 2+ signals agreeing).")
        return

    logger.info("")
    logger.info("=" * 72)
    logger.info("  HIDDEN GEMS — Stocks with multiple independent signals")
    logger.info("=" * 72)
    for g in gems:
        sigs = ", ".join(g.active_signals)
        logger.info("")
        logger.info("  %s  [%d signals: %s]", g.ticker, len(g.active_signals), sigs)
        for r in g.reasons[:5]:
            logger.info("    • %s", r)
        if g.fundamental:
            logger.info("    Fundamental: score=%s mcap=$%.1fB growth=%s EV/S=%s",
                        g.fundamental["score"],
                        g.fundamental["mcap"] / 1e9 if g.fundamental["mcap"] else 0,
                        f"{g.fundamental['growth']:.0%}" if g.fundamental["growth"] else "N/A",
                        f"{g.fundamental['ev_sales']:.1f}" if g.fundamental["ev_sales"] else "N/A")
        if g.earnings:
            logger.info("    Earnings: surprise=%+.1f%% on %s",
                        g.earnings["surprise_pct"], g.earnings["date"])
        if g.insider:
            logger.info("    Insider: %d buyers, $%s total",
                        g.insider["buyers"], f"{g.insider['buy_value']:,.0f}")
        if g.squeeze:
            logger.info("    Squeeze: SI=%s%% vol=%s×",
                        g.squeeze.get("short_pct", "N/A"), g.squeeze.get("vol_mult", "N/A"))
        if g.volume:
            logger.info("    Volume: score=%s vol=%s× OBV_brk=%s",
                        g.volume["score"], g.volume["vol_mult"],
                        "Y" if g.volume.get("obv_breakout") else "N")
    logger.info("")
    logger.info("=" * 72)
    logger.info("  Total: %d gems found from universe scan", len(gems))
    logger.info("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Hidden Gem Scanner")
    parser.add_argument("--tickers", nargs="+", help="Override universe")
    parser.add_argument("--min-signals", type=int, default=MIN_SIGNALS_FOR_GEM)
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] if args.tickers else None
    gems = scan_universe(tickers, min_signals=args.min_signals)
    print_results(gems)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
