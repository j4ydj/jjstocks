#!/usr/bin/env python3
"""
MARKET-WIDE EDGE SCANNER
========================
Scans the entire market (500+ stocks) with intelligent prioritization.
Uses yfinance screener + rate-limited batch processing.
"""
import logging
import time
from typing import List, Set, Dict
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Comprehensive universe - all actionable stocks
FULL_UNIVERSE = {
    # Mega-cap tech
    "tech_mega": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "TSM",
        "JPM", "V", "MA", "UNH", "LLY", "JNJ", "XOM", "WMT", "PG", "HD", "CVX",
        "MRK", "ABBV", "BAC", "KO", "PEP", "PFE", "COST", "TMO", "ABT", "DHR",
        "ORCL", "CRM", "ADBE", "ACN", "NFLX", "AMD", "INTC", "QCOM", "TXN", "AMAT",
    ],
    # High-volatility growth (best for edges)
    "high_vol_growth": [
        "PLTR", "MSTR", "COIN", "HOOD", "CRWD", "SNOW", "DDOG", "NET", "ZS", "OKTA",
        "MDB", "GTLB", "S", "IOT", "BRZE", "CFLT", "DOCN", "DT", "PD", "VEEV",
        "ZS", "OKTA", "CYBR", "SPLK", "NOW", "TEAM", "ATLASSIAN", "ASAN", "MONDAY",
        "UPST", "SOFI", "AFRM", "LMND", "ROOT", "HCP", "DOCS", "TDOC", "AMWL", "CLOV",
        "RBLX", "U", "MTTR", "VZIO", "CURI", "PTON", "ETSY", "SQ", "SHOP", "BIGC",
    ],
    # Meme/momentum stocks (retail attention)
    "meme_momentum": [
        "GME", "AMC", "BB", "NOK", "EXPR", "KOSS", "NAKD", "BBBY", "SPRT", "TR",
        "SNDL", "TLRY", "ACB", "CRON", "CGC", "HEXO", "OGI", "GNLN", "APHA", "MWK",
        "DWAC", "PHUN", "CFVI", "RUM", "BENE", "MARK", "XELA", "CEI", "FAMI", "NIO",
        "LCID", "RIVN", "FSR", "GOEV", "HYLN", "NKLA", "MULN", "RIDE", "ARVL", "Canoo",
        "RKLB", "SPCE", "ASTS", "ASTR", "MNTS", "SRAC", "NPA", "NGCA", "VORB", "REDWIRE",
    ],
    # Biotech (earnings surprise potential)
    "biotech": [
        "MRNA", "BNTX", "NVAX", "PFE", "JNJ", "ABBV", "LLY", "MRK", "AMGN", "GILD",
        "REGN", "BIIB", "VRTX", "ALNY", "IONS", "SRPT", "BMRN", "NTRA", "EXAS", "GH",
        "TGTX", "KPTI", "PTCT", "RARE", "FOLD", "ARWR", "NTLA", "EDIT", "CRSP", "BEAM",
        "HALO", "PCVX", "ADCT", "ARVN", "RCKT", "SRNE", "INO", "VXRT", "COCP", "EBS",
    ],
    # Energy/Commodities (macro sensitive)
    "energy_commodities": [
        "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "MPC", "VLO", "PSX", "WMB",
        "KMI", "OKE", "EPD", "ET", "MPLX", "ENB", "TRP", "LNG", "CPNG", "CHK",
        "USO", "UNG", "GLD", "SLV", "PDBC", "DBA", "WEAT", "CORN", "SOYB", "BNO",
        "CL=F", "NG=F", "GC=F", "SI=F", "ZW=F", "ZC=F", "ZS=F", "KC=F", "CT=F", "CC=F",
    ],
    # Crypto-adjacent
    "crypto": [
        "COIN", "MSTR", "RIOT", "MARA", "HUT", "BITF", "CLSK", "ARBK", "CORZ", "SDIG",
        "GLXY", "BTBT", "HIVE", "BITF", "WULF", "IREN", "BTDR", "CIFR", "SLNH", "SATO",
        "BITO", "BITI", "XBTF", "BTF", "ARKW", "ARKF", "ARKK", "WGMI", "CRPT", "DAPP",
    ],
    # ARK / Cathie Wood universe
    "ark_innovation": [
        "TSLA", "ROKU", "CRSP", "SQ", "Z", "SPOT", "PRLB", "TREE", "TWLO", "SQ",
        "EXAS", "TDOC", "NTLA", "VCYT", "IOVA", "TRMB", "SSYS", "DDD", "MTLS", "XONE",
        "IRDM", "LMT", "BA", "TXT", "AJRD", "SPCE", "ACHR", "JOBY", "LILM", "EH",
        "DKNG", "ROBLOX", "UNITY", "MTTR", "VZIO", "CUR", "EDIT", "TWST", "PACB", "BEAM",
    ],
    # S&P 500 liquid names (for safety)
    "sp500_liquid": [
        "SPY", "VOO", "IVV", "QQQ", "IWM", "DIA", "VTI", "VTV", "VUG", "VB",
        "VEA", "VWO", "BND", "AGG", "LQD", "HYG", "TLT", "IEF", "SHY", "GLD",
        "XLF", "XLK", "XLE", "XLU", "XLI", "XLP", "XLB", "XRT", "XBI", "XHB",
        "SMH", "SOXX", "XSD", "FINX", "AIQ", "BOTZ", "ROBO", "DRIV", "IDRV", "HAIL",
    ],
    # International / Emerging
    "international": [
        "BABA", "TCEHY", "JD", "PDD", "NIO", "LI", "XPEV", "BYDDF", "DIDI", "EDU",
        "TME", "YY", "MOMO", "BZ", "ATHM", "VIPS", "JOBS", "STX", "UMC", "ASML",
        "SAP", "SHEL", "TM", "HMC", "SONY", "NTDOY", "EADSY", "LVMUY", "NVO", "AZN",
        "GSK", "SFTBY", "AMX", "VALE", "PBR", "ITUB", "ABEV", "GOL", "AZUL", "CPA",
    ],
    # SPACs / De-SPACs
    "spacs": [
        "CCIV", "IPOE", "IPOD", "IPOF", "SPAQ", "GHIV", "BFT", "NGCA", "ASPC", "ROCR",
        "LCAP", "GNPK", "AGCB", "ETAC", "BSN", "SCPE", "HERA", "DUNE", "FPAC", "RBAC",
    ],
}

# Flatten to unique list
def get_full_universe() -> List[str]:
    """Get deduplicated full universe."""
    seen = set()
    universe = []
    for category, tickers in FULL_UNIVERSE.items():
        for ticker in tickers:
            if ticker not in seen:
                seen.add(ticker)
                universe.append(ticker)
    return universe

def get_priority_universe() -> List[str]:
    """
    High-priority tickers most likely to produce edges.
    Best signal-to-noise ratio.
    """
    # Priority order: high vol growth > meme > biotech > crypto > tech mega
    priority = []
    
    # These categories have the best edge potential
    priority.extend(FULL_UNIVERSE["high_vol_growth"][:40])
    priority.extend(FULL_UNIVERSE["meme_momentum"][:30])
    priority.extend(FULL_UNIVERSE["biotech"][:30])
    priority.extend(FULL_UNIVERSE["crypto"][:20])
    priority.extend(FULL_UNIVERSE["tech_mega"][:30])
    priority.extend(FULL_UNIVERSE["ark_innovation"][:20])
    
    return list(dict.fromkeys(priority))  # Dedupe while preserving order

class MarketWideScanner:
    """
    Scans hundreds of tickers with rate limiting and progress tracking.
    """
    
    def __init__(self, delay: float = 0.3):
        """
        Args:
            delay: Seconds between ticker requests (avoid rate limits)
        """
        self.delay = delay
        self.processed = 0
        self.errors = 0
        self.signals_found = 0
    
    def scan(self, universe: List[str], min_score: int = 2, max_tickers: int = None) -> List[Dict]:
        """
        Scan universe and return signals.
        
        Args:
            universe: List of tickers
            min_score: Minimum signal score to report
            max_tickers: Limit scan size (None = all)
        """
        from working_edge_system import WorkingEdgeSystem
        
        system = WorkingEdgeSystem()
        
        if max_tickers:
            universe = universe[:max_tickers]
        
        total = len(universe)
        signals = []
        
        logger.info(f"=" * 70)
        logger.info(f"  MARKET-WIDE SCAN")
        logger.info(f"  Tickers: {total} | Min Score: {min_score} | Delay: {self.delay}s")
        logger.info(f"=" * 70)
        
        start_time = time.time()
        
        for i, ticker in enumerate(universe, 1):
            try:
                signal = system.score_ticker(ticker)
                
                if signal and abs(signal.score) >= min_score:
                    signals.append({
                        "ticker": signal.ticker,
                        "score": signal.score,
                        "direction": signal.direction,
                        "confidence": signal.confidence,
                        "sources": signal.sources,
                        "catalyst": signal.catalyst
                    })
                    self.signals_found += 1
                
                self.processed += 1
                
                # Progress report every 20 tickers
                if i % 20 == 0 or i == total:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    logger.info(f"  Progress: {i}/{total} | "
                              f"Signals: {self.signals_found} | "
                              f"Rate: {rate:.1f}/s | "
                              f"ETA: {(total-i)/rate:.0f}s" if rate > 0 else "")
                
                # Rate limiting
                if i < total:  # Don't delay after last
                    time.sleep(self.delay)
                
            except Exception as e:
                self.errors += 1
                if self.errors <= 5:  # Only log first few errors
                    logger.debug(f"Error on {ticker}: {e}")
                continue
        
        # Sort by absolute score
        signals.sort(key=lambda x: abs(x["score"]), reverse=True)
        
        # Summary
        elapsed = time.time() - start_time
        logger.info(f"\n{'='*70}")
        logger.info(f"  SCAN COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"  Processed: {self.processed}/{total}")
        logger.info(f"  Errors: {self.errors}")
        logger.info(f"  Signals found: {len(signals)}")
        logger.info(f"  Time: {elapsed:.0f}s ({self.processed/elapsed:.1f} tickers/s)" if elapsed > 0 else "")
        
        return signals
    
    def scan_category(self, category: str, **kwargs) -> List[Dict]:
        """Scan specific category."""
        if category not in FULL_UNIVERSE:
            logger.error(f"Unknown category: {category}")
            logger.info(f"Available: {list(FULL_UNIVERSE.keys())}")
            return []
        
        return self.scan(FULL_UNIVERSE[category], **kwargs)

def main():
    """Run market-wide scan."""
    import json
    
    scanner = MarketWideScanner(delay=0.3)  # 0.3s delay to avoid rate limits
    
    # Option 1: Full universe (takes ~10-15 minutes)
    # universe = get_full_universe()
    # signals = scanner.scan(universe, min_score=2, max_tickers=200)
    
    # Option 2: Priority universe (best edge potential, ~5 minutes)
    universe = get_priority_universe()
    logger.info(f"Priority universe: {len(universe)} tickers")
    signals = scanner.scan(universe, min_score=2)
    
    # Option 3: Single category
    # signals = scanner.scan_category("meme_momentum", min_score=1)
    
    # Export results
    if signals:
        # Separate by direction
        longs = [s for s in signals if s["direction"] == "LONG"]
        shorts = [s for s in signals if s["direction"] == "SHORT"]
        avoids = [s for s in signals if s["direction"] == "AVOID"]
        
        output = {
            "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "universe_size": len(universe),
            "min_score": 2,
            "total_signals": len(signals),
            "longs": longs[:10],
            "shorts": shorts[:5],
            "avoids": avoids[:5],
            "all_signals": signals
        }
        
        with open("market_scan_results.json", "w") as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"\n💾 Exported {len(signals)} signals to market_scan_results.json")
        
        # Display top picks
        if longs:
            logger.info(f"\n🚀 Top LONGS:")
            for s in longs[:5]:
                logger.info(f"  {s['ticker']}: +{s['score']} ({s['confidence']}) - {s['catalyst'][:40]}")
        
        if avoids:
            logger.info(f"\n⚠️  Top AVOIDS:")
            for s in avoids[:3]:
                logger.info(f"  {s['ticker']}: {s['score']} - {s['catalyst'][:40]}")
    else:
        logger.info("\nNo signals above threshold found.")

if __name__ == "__main__":
    main()
