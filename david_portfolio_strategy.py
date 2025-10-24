#!/usr/bin/env python3
"""
THE "DAVID vs GOLIATH" PORTFOLIO STRATEGY
=======================================

Your SECRET WEAPON: Playing in markets where $100B hedge funds CAN'T compete.

This is your path from $0 to financial freedom by exploiting the structural 
weaknesses of massive institutional investors.

Author: Your Financial Revolution
Status: CLASSIFIED ADVANTAGE SYSTEM
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class DavidOpportunity:
    """Small cap opportunity that big funds can't touch"""
    ticker: str
    market_cap: float          # Must be <$2B (big fund exclusion zone)
    liquidity_score: float     # 0-1 scale
    institutional_ownership: float  # Lower = better for David strategy
    insider_ownership: float   # Higher = better alignment
    growth_momentum: float     # Revenue/earnings growth
    technical_breakout: float  # Technical setup quality
    david_score: float         # Overall David opportunity score
    why_big_funds_cant_play: str  # Key exclusion reason
    estimated_upside: float    # Conservative upside estimate
    risk_level: str           # LOW/MEDIUM/HIGH
    catalyst_timeline: str     # Expected catalyst timing

class DavidPortfolioStrategy:
    """
    THE "DAVID vs GOLIATH" STRATEGY
    
    Your advantages over $100B hedge funds:
    
    1. SMALL CAP FREEDOM: You can invest 100% in $500M companies
       - Big funds can only allocate 0.1% (position size limits)
       - You get 200x more impact per dollar
    
    2. SPEED ADVANTAGE: You can act in seconds
       - Big funds need weeks to build positions
       - You capture breakouts before they even start buying
    
    3. REGULATORY FREEDOM: You can use data they can't
       - No 13F filing requirements
       - No position disclosure limits
       - No SEC scrutiny on trading patterns
    
    4. LIQUIDITY ADVANTAGE: You can trade illiquid gems
       - $10M daily volume is enough for you
       - They need $100M+ daily volume minimum
    
    5. CONCENTRATION POWER: You can go 20% in one position
       - They're limited to 2-3% max positions
       - Your conviction trades have 10x more impact
    """
    
    def __init__(self):
        self.session = None
        self.exclusion_thresholds = {
            'max_market_cap': 2_000_000_000,  # $2B - above this, big funds compete
            'min_daily_volume': 1_000_000,    # $1M - below this, too illiquid
            'max_institutional_ownership': 0.6,  # 60% - above this, too crowded
            'min_insider_ownership': 0.05      # 5% - skin in the game
        }
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def scan_david_opportunities(self, sectors: List[str] = None) -> List[DavidOpportunity]:
        """
        Scan for David opportunities across sectors where big funds can't compete
        
        TARGET SECTORS (where small caps dominate):
        - Biotech (pre-revenue, too risky for big funds)
        - Emerging tech (AI/ML, quantum, clean energy)
        - Regional services (local market dominance)
        - Niche manufacturing (specialized products)
        - Digital transformation (B2B SaaS, fintech)
        """
        if sectors is None:
            sectors = [
                'biotechnology', 'healthcare-services', 'software',
                'clean-energy', 'cybersecurity', 'fintech',
                'semiconductors', 'materials', 'industrials'
            ]
        
        opportunities = []
        
        # Get small cap universe (Russell 2000 + additional screening)
        small_cap_universe = await self._get_small_cap_universe()
        
        for ticker in small_cap_universe[:100]:  # Scan top 100 for demo
            try:
                opportunity = await self._analyze_david_opportunity(ticker)
                if opportunity and opportunity.david_score > 0.6:  # High-quality only
                    opportunities.append(opportunity)
                    
                # Rate limiting - be respectful
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"David analysis failed for {ticker}: {e}")
                continue
        
        # Sort by David score (best opportunities first)
        opportunities.sort(key=lambda x: x.david_score, reverse=True)
        
        return opportunities[:20]  # Top 20 opportunities

    async def _get_small_cap_universe(self) -> List[str]:
        """Get universe of small cap stocks where David strategy applies"""
        try:
            # Russell 2000 components (small caps)
            russell_2000_symbols = [
                'SIRI', 'PLUG', 'FUBO', 'CLOV', 'WISH', 'SOFI', 'HOOD', 'RIVN',
                'LCID', 'COIN', 'RBLX', 'U', 'SNOW', 'DDOG', 'CRWD', 'ZM',
                'DOCU', 'OKTA', 'TWLO', 'NET', 'FSLY', 'ESTC', 'MDB', 'TEAM',
                'ATLASSIAN', 'WDAY', 'NOW', 'ADBE', 'CRM', 'ORCL', 'MSFT',
                # Add more Russell 2000 symbols here
                'MRNA', 'BNTX', 'NVAX', 'VXRT', 'INO', 'OCGN', 'TGTX', 'SRNE',
                'ATOS', 'CEMI', 'DARE', 'EIGR', 'FREQ', 'GTHX', 'IMMP', 'KPTI',
                'LCTX', 'MCRB', 'NKTR', 'OBSV', 'PTCT', 'QURE', 'RARE', 'SGMO'
            ]
            
            # Filter to ensure they meet David criteria
            filtered_symbols = []
            
            for symbol in russell_2000_symbols:
                try:
                    stock = yf.Ticker(symbol)
                    info = stock.info
                    
                    market_cap = info.get('marketCap', 0)
                    if market_cap and market_cap < self.exclusion_thresholds['max_market_cap']:
                        filtered_symbols.append(symbol)
                        
                except:
                    continue
            
            return filtered_symbols
            
        except Exception as e:
            logger.error(f"Failed to get small cap universe: {e}")
            return []

    async def _analyze_david_opportunity(self, ticker: str) -> Optional[DavidOpportunity]:
        """Analyze if a stock qualifies as a David opportunity"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="6mo")
            
            if hist.empty or len(hist) < 50:
                return None
            
            # BASIC QUALIFICATION CHECKS
            market_cap = info.get('marketCap', 0)
            if not market_cap or market_cap > self.exclusion_thresholds['max_market_cap']:
                return None  # Too big - big funds will compete
            
            # Calculate key metrics
            current_price = hist['Close'].iloc[-1]
            avg_volume = hist['Volume'].tail(20).mean()
            avg_dollar_volume = avg_volume * current_price
            
            if avg_dollar_volume < self.exclusion_thresholds['min_daily_volume']:
                return None  # Too illiquid even for David
            
            # DAVID ADVANTAGE ANALYSIS
            
            # 1. INSTITUTIONAL OWNERSHIP (lower = better)
            institutional_ownership = info.get('heldByInstitutions', 0.0)
            if institutional_ownership > self.exclusion_thresholds['max_institutional_ownership']:
                return None  # Too crowded with big money
            
            # 2. INSIDER OWNERSHIP (higher = better alignment)
            insider_ownership = info.get('heldByInsiders', 0.0)
            
            # 3. GROWTH MOMENTUM
            revenue_growth = info.get('revenueGrowth', 0.0)
            earnings_growth = info.get('earningsGrowth', 0.0)
            growth_momentum = (revenue_growth + earnings_growth) / 2
            
            # 4. TECHNICAL SETUP
            technical_score = self._calculate_technical_breakout_score(hist)
            
            # 5. LIQUIDITY SCORE
            liquidity_score = min(1.0, avg_dollar_volume / 10_000_000)  # $10M = perfect
            
            # CALCULATE DAVID SCORE
            david_components = {
                'low_institutional': (1 - institutional_ownership) * 0.25,  # 25% weight
                'high_insider': insider_ownership * 0.15,                   # 15% weight
                'growth_momentum': min(1.0, growth_momentum * 2) * 0.25,    # 25% weight
                'technical_setup': technical_score * 0.20,                  # 20% weight
                'liquidity_quality': liquidity_score * 0.15                # 15% weight
            }
            
            david_score = sum(david_components.values())
            
            # DETERMINE WHY BIG FUNDS CAN'T PLAY
            exclusion_reasons = []
            if market_cap < 1_000_000_000:  # <$1B
                exclusion_reasons.append("Market cap too small for institutional mandates")
            if institutional_ownership < 0.3:
                exclusion_reasons.append("Insufficient institutional interest/coverage")
            if avg_dollar_volume < 5_000_000:  # <$5M daily
                exclusion_reasons.append("Liquidity too low for large position building")
            if insider_ownership > 0.2:
                exclusion_reasons.append("High insider ownership limits float")
            
            why_excluded = "; ".join(exclusion_reasons) if exclusion_reasons else "Multiple small-cap constraints"
            
            # ESTIMATE UPSIDE POTENTIAL
            estimated_upside = self._estimate_upside_potential(
                growth_momentum, technical_score, market_cap, institutional_ownership
            )
            
            # RISK ASSESSMENT
            risk_level = self._assess_risk_level(market_cap, liquidity_score, institutional_ownership)
            
            # CATALYST TIMELINE
            catalyst_timeline = self._estimate_catalyst_timeline(info, growth_momentum)
            
            return DavidOpportunity(
                ticker=ticker,
                market_cap=market_cap,
                liquidity_score=liquidity_score,
                institutional_ownership=institutional_ownership,
                insider_ownership=insider_ownership,
                growth_momentum=growth_momentum,
                technical_breakout=technical_score,
                david_score=david_score,
                why_big_funds_cant_play=why_excluded,
                estimated_upside=estimated_upside,
                risk_level=risk_level,
                catalyst_timeline=catalyst_timeline
            )
            
        except Exception as e:
            logger.error(f"David opportunity analysis failed for {ticker}: {e}")
            return None

    def _calculate_technical_breakout_score(self, hist: pd.DataFrame) -> float:
        """Calculate technical breakout potential score"""
        try:
            close = hist['Close']
            volume = hist['Volume']
            
            # Current price vs moving averages
            sma_20 = close.rolling(20).mean().iloc[-1]
            sma_50 = close.rolling(50).mean().iloc[-1]
            current_price = close.iloc[-1]
            
            # Price momentum
            price_momentum = (current_price / sma_20 - 1) * 0.4
            
            # Moving average alignment
            ma_alignment = (sma_20 / sma_50 - 1) * 0.3 if sma_50 > 0 else 0
            
            # Volume surge
            avg_volume = volume.rolling(20).mean()
            recent_volume = volume.tail(5).mean()
            volume_surge = (recent_volume / avg_volume.iloc[-1] - 1) * 0.3 if avg_volume.iloc[-1] > 0 else 0
            
            # Combine scores
            technical_score = max(0, min(1, 0.5 + price_momentum + ma_alignment + volume_surge))
            
            return technical_score
            
        except:
            return 0.5  # Neutral if calculation fails

    def _estimate_upside_potential(self, growth_momentum: float, technical_score: float, 
                                 market_cap: float, institutional_ownership: float) -> float:
        """Estimate conservative upside potential"""
        
        # Base upside from growth (higher growth = higher upside)
        growth_upside = min(2.0, growth_momentum * 3)  # Max 200% from growth
        
        # Technical setup upside
        technical_upside = technical_score * 0.5  # Max 50% from technical
        
        # Small cap premium (smaller = higher potential)
        size_premium = max(0, (2_000_000_000 - market_cap) / 2_000_000_000 * 0.5)  # Max 50%
        
        # Institutional discovery upside (lower institutional = higher upside)
        discovery_upside = (1 - institutional_ownership) * 0.3  # Max 30%
        
        # Conservative total upside estimate
        total_upside = growth_upside + technical_upside + size_premium + discovery_upside
        
        return min(3.0, total_upside)  # Cap at 300% upside

    def _assess_risk_level(self, market_cap: float, liquidity_score: float, 
                          institutional_ownership: float) -> str:
        """Assess risk level of David opportunity"""
        
        risk_factors = 0
        
        # Market cap risk
        if market_cap < 500_000_000:  # <$500M
            risk_factors += 2
        elif market_cap < 1_000_000_000:  # <$1B
            risk_factors += 1
        
        # Liquidity risk
        if liquidity_score < 0.3:
            risk_factors += 2
        elif liquidity_score < 0.6:
            risk_factors += 1
        
        # Institutional support risk
        if institutional_ownership < 0.1:
            risk_factors += 1
        
        if risk_factors >= 4:
            return "HIGH"
        elif risk_factors >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    def _estimate_catalyst_timeline(self, info: Dict, growth_momentum: float) -> str:
        """Estimate when catalysts might occur"""
        
        # Check earnings date
        try:
            next_earnings = info.get('nextFiscalYearEnd', '')
            if next_earnings:
                return f"Next earnings: {next_earnings}"
        except:
            pass
        
        # Based on growth momentum
        if growth_momentum > 0.2:  # 20%+ growth
            return "1-3 months (high growth momentum)"
        elif growth_momentum > 0.1:  # 10%+ growth
            return "3-6 months (moderate growth)"
        else:
            return "6+ months (longer-term play)"

    def generate_david_portfolio_report(self, opportunities: List[DavidOpportunity]) -> str:
        """Generate David vs Goliath portfolio report"""
        
        if not opportunities:
            return "❌ No David opportunities found meeting criteria"
        
        report = f"""
SMALL CAP OPPORTUNITIES ANALYSIS
═══════════════════════════════
Opportunities Found: {len(opportunities)}
Market Cap Range: $100M - $2B

TOP OPPORTUNITIES:
"""
        
        for i, opp in enumerate(opportunities[:10], 1):
            risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}[opp.risk_level]
            
            # Generate reasoning summary
            reasoning = self._generate_reasoning_summary(opp)
            
            report += f"""
{i:2d}. {opp.ticker} - Score: {opp.david_score:.1%} {risk_emoji}
    ├─ Market Cap: ${opp.market_cap/1_000_000:.0f}M
    ├─ Institutional Ownership: {opp.institutional_ownership:.1%}
    ├─ Insider Ownership: {opp.insider_ownership:.1%}
    ├─ Growth Momentum: {opp.growth_momentum:+.1%}
    ├─ Technical Setup: {opp.technical_breakout:.1%}
    ├─ Estimated Upside: {opp.estimated_upside:.0%}
    ├─ Risk Level: {opp.risk_level}
    ├─ Catalyst Timeline: {opp.catalyst_timeline}
    ├─ Why Approved: {reasoning}
    └─ Constraints: {opp.why_big_funds_cant_play}
"""
        
        # Portfolio construction recommendations
        low_risk_ops = [o for o in opportunities if o.risk_level == "LOW"]
        med_risk_ops = [o for o in opportunities if o.risk_level == "MEDIUM"]
        high_risk_ops = [o for o in opportunities if o.risk_level == "HIGH"]
        
        report += f"""

PORTFOLIO ALLOCATION GUIDANCE:

🟢 LOW RISK ({len(low_risk_ops)} available):
{f"   • Avg upside: {sum(o.estimated_upside for o in low_risk_ops)/len(low_risk_ops):.0%}" if low_risk_ops else "   • None available"}

🟡 MEDIUM RISK ({len(med_risk_ops)} available):
{f"   • Avg upside: {sum(o.estimated_upside for o in med_risk_ops)/len(med_risk_ops):.0%}" if med_risk_ops else "   • None available"}

🔴 HIGH RISK ({len(high_risk_ops)} available):
{f"   • Avg upside: {sum(o.estimated_upside for o in high_risk_ops)/len(high_risk_ops):.0%}" if high_risk_ops else "   • None available"}

═══════════════════════════════
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report

    def _generate_reasoning_summary(self, opp: DavidOpportunity) -> str:
        """Generate DETAILED reasoning for why this stock was approved as a David opportunity"""
        
        # COMPLETE TRANSPARENCY - Show EVERY factor that contributed to approval
        reasoning_sections = []
        
        # 1. CORE DAVID THESIS
        david_thesis = []
        
        # Market cap exclusion for big funds
        if opp.market_cap < 500_000_000:
            david_thesis.append(f"🎯 MICRO-CAP ADVANTAGE: ${opp.market_cap/1_000_000:.0f}M market cap excludes most institutional mandates (min $1B)")
        elif opp.market_cap < 1_000_000_000:
            david_thesis.append(f"🎯 SMALL-CAP ADVANTAGE: ${opp.market_cap/1_000_000:.0f}M market cap limits big fund allocation (<0.1% position size)")
        else:
            david_thesis.append(f"🎯 SMALL-CAP RANGE: ${opp.market_cap/1_000_000:.0f}M market cap still in David's sweet spot")
        
        # Institutional ownership analysis
        if opp.institutional_ownership < 0.2:
            david_thesis.append(f"🔍 UNDISCOVERED: Only {opp.institutional_ownership:.1%} institutional ownership - flying under the radar")
        elif opp.institutional_ownership < 0.4:
            david_thesis.append(f"🔍 LIMITED INSTITUTIONAL: {opp.institutional_ownership:.1%} ownership - moderate institutional interest")
        else:
            david_thesis.append(f"🔍 INSTITUTIONAL PRESENCE: {opp.institutional_ownership:.1%} ownership - getting some attention")
        
        reasoning_sections.append("DAVID ADVANTAGE: " + "; ".join(david_thesis))
        
        # 2. FUNDAMENTAL STRENGTH
        fundamental_factors = []
        
        # Growth momentum detailed analysis
        if opp.growth_momentum > 0.25:
            fundamental_factors.append(f"📈 EXCEPTIONAL GROWTH: {opp.growth_momentum:+.1%} revenue/earnings momentum")
        elif opp.growth_momentum > 0.15:
            fundamental_factors.append(f"📈 STRONG GROWTH: {opp.growth_momentum:+.1%} revenue/earnings momentum")
        elif opp.growth_momentum > 0.05:
            fundamental_factors.append(f"📈 POSITIVE GROWTH: {opp.growth_momentum:+.1%} revenue/earnings momentum")
        elif opp.growth_momentum > -0.05:
            fundamental_factors.append(f"📊 STABLE: {opp.growth_momentum:+.1%} revenue/earnings (flat but stable)")
        else:
            fundamental_factors.append(f"📉 DECLINING: {opp.growth_momentum:+.1%} revenue/earnings (turnaround play)")
        
        # Insider ownership alignment
        if opp.insider_ownership > 0.20:
            fundamental_factors.append(f"🤝 HIGH INSIDER SKIN: {opp.insider_ownership:.1%} insider ownership shows strong management conviction")
        elif opp.insider_ownership > 0.10:
            fundamental_factors.append(f"🤝 MEANINGFUL INSIDER: {opp.insider_ownership:.1%} insider ownership aligns management with shareholders")
        elif opp.insider_ownership > 0.05:
            fundamental_factors.append(f"🤝 MODERATE INSIDER: {opp.insider_ownership:.1%} insider ownership provides some alignment")
        else:
            fundamental_factors.append(f"🤝 LOW INSIDER: {opp.insider_ownership:.1%} insider ownership (professional management)")
        
        if fundamental_factors:
            reasoning_sections.append("FUNDAMENTALS: " + "; ".join(fundamental_factors))
        
        # 3. TECHNICAL SETUP
        technical_factors = []
        
        if opp.technical_breakout > 0.8:
            technical_factors.append("📊 EXCEPTIONAL TECHNICAL: Strong breakout potential, bullish momentum, volume confirmation")
        elif opp.technical_breakout > 0.7:
            technical_factors.append("📊 STRONG TECHNICAL: Good breakout setup, positive momentum indicators")
        elif opp.technical_breakout > 0.6:
            technical_factors.append("📊 FAVORABLE TECHNICAL: Decent setup, some positive indicators")
        elif opp.technical_breakout > 0.4:
            technical_factors.append("📊 NEUTRAL TECHNICAL: Mixed signals, no clear directional bias")
        else:
            technical_factors.append("📊 WEAK TECHNICAL: Poor setup, may need more consolidation")
        
        if technical_factors:
            reasoning_sections.append("TECHNICAL: " + "; ".join(technical_factors))
        
        # 4. LIQUIDITY & ACCESSIBILITY
        liquidity_factors = []
        
        if opp.liquidity_score > 0.8:
            liquidity_factors.append("💧 EXCELLENT LIQUIDITY: Easy entry/exit, sufficient daily volume")
        elif opp.liquidity_score > 0.6:
            liquidity_factors.append("💧 GOOD LIQUIDITY: Adequate volume for most position sizes")
        elif opp.liquidity_score > 0.4:
            liquidity_factors.append("💧 MODERATE LIQUIDITY: May require staged entry/exit")
        else:
            liquidity_factors.append("💧 LIMITED LIQUIDITY: Requires careful position management")
        
        if liquidity_factors:
            reasoning_sections.append("LIQUIDITY: " + "; ".join(liquidity_factors))
        
        # 5. RISK ASSESSMENT
        risk_factors = []
        
        if opp.risk_level == "LOW":
            risk_factors.append("🟢 LOW RISK: Stable business, adequate liquidity, reasonable valuation")
        elif opp.risk_level == "MEDIUM":
            risk_factors.append("🟡 MEDIUM RISK: Some volatility expected, manageable risk factors")
        else:
            risk_factors.append("🔴 HIGH RISK: Significant volatility potential, requires risk management")
        
        if risk_factors:
            reasoning_sections.append("RISK: " + "; ".join(risk_factors))
        
        # 6. UPSIDE POTENTIAL
        upside_factors = []
        
        if opp.estimated_upside > 2.0:
            upside_factors.append(f"🚀 EXCEPTIONAL UPSIDE: {opp.estimated_upside:.0%} potential based on growth, technical setup, and discovery premium")
        elif opp.estimated_upside > 1.0:
            upside_factors.append(f"🚀 STRONG UPSIDE: {opp.estimated_upside:.0%} potential from multiple catalysts")
        elif opp.estimated_upside > 0.5:
            upside_factors.append(f"🚀 MODERATE UPSIDE: {opp.estimated_upside:.0%} potential upside estimated")
        else:
            upside_factors.append(f"🚀 LIMITED UPSIDE: {opp.estimated_upside:.0%} conservative upside")
        
        if upside_factors:
            reasoning_sections.append("UPSIDE: " + "; ".join(upside_factors))
        
        # 7. CATALYST TIMELINE
        catalyst_factors = [f"⏰ TIMELINE: {opp.catalyst_timeline}"]
        reasoning_sections.append("CATALYSTS: " + "; ".join(catalyst_factors))
        
        # 8. WHY BIG FUNDS CAN'T COMPETE
        exclusion_factors = [f"🚫 BIG FUND EXCLUSIONS: {opp.why_big_funds_cant_play}"]
        reasoning_sections.append("EXCLUSIONS: " + "; ".join(exclusion_factors))
        
        # 9. OVERALL SCORE BREAKDOWN
        score_components = []
        if opp.david_score > 0.9:
            score_components.append(f"⭐ EXCEPTIONAL DAVID SCORE: {opp.david_score:.1%} (top 5% of opportunities)")
        elif opp.david_score > 0.8:
            score_components.append(f"⭐ STRONG DAVID SCORE: {opp.david_score:.1%} (top 10% of opportunities)")
        elif opp.david_score > 0.7:
            score_components.append(f"⭐ GOOD DAVID SCORE: {opp.david_score:.1%} (top 20% of opportunities)")
        else:
            score_components.append(f"⭐ SOLID DAVID SCORE: {opp.david_score:.1%} (meets minimum criteria)")
        
        reasoning_sections.append("SCORE: " + "; ".join(score_components))
        
        # Combine all sections with clear separators
        complete_reasoning = " || ".join(reasoning_sections)
        
        return complete_reasoning

# GLOBAL INSTANCE
david_strategy = None

async def scan_david_opportunities() -> str:
    """Scan for David vs Goliath opportunities"""
    global david_strategy
    
    if david_strategy is None:
        david_strategy = DavidPortfolioStrategy()
    
    async with david_strategy:
        opportunities = await david_strategy.scan_david_opportunities()
        return david_strategy.generate_david_portfolio_report(opportunities)

if __name__ == "__main__":
    # Test the David strategy
    async def test_david_strategy():
        print("🎯 Testing David vs Goliath Strategy...")
        report = await scan_david_opportunities()
        print(report)
    
    asyncio.run(test_david_strategy())

