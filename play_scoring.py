"""Score and rank trade plays 0–100 for alerting."""
from typing import List, Optional

from momentum_chain import MomentumChain, ChainLink

PLAY_TYPE_BONUS = {
    "pullback": 8,
    "catch_up": 6,
    "downstream": 5,
    "chain_trend": 4,
    "thematic_basket": 3,
    "relative_spread": 7,
}


def score_play(
    play,
    chain: Optional[MomentumChain] = None,
    regime: str = "neutral",
) -> int:
    s = 40.0
    s += play.conviction * 10
    s += min(20.0, play.risk_reward * 6)
    s += PLAY_TYPE_BONUS.get(play.play_type, 0)

    if regime == "neutral":
        s += 5
    elif play.direction == "BUY" and regime == "risk_on":
        s += 8
    elif play.direction == "SHORT" and regime == "risk_off":
        s += 8
    elif play.direction == "BUY" and regime == "risk_off":
        s -= 25
    elif play.direction == "SHORT" and regime == "risk_on":
        s -= 15

    if chain:
        p = chain.focus
        if play.direction == "BUY" and p.return_5d_pct > 5:
            s += 5
        if play.direction == "SHORT" and p.return_5d_pct < -5:
            s += 5
        if play.play_type == "pullback" and p.return_5d_pct > 6 and p.return_1d_pct < -2:
            s += 10

    return max(0, min(100, int(round(s))))


def rank_plays(
    plays: List,
    chains: Optional[List[MomentumChain]] = None,
    regimes: Optional[dict] = None,
    top_n: int = 5,
) -> List:
    chain_by_ticker = {c.focus.ticker: c for c in (chains or [])}
    scored = []
    for pl in plays:
        ch = chain_by_ticker.get(pl.ticker)
        reg = (regimes or {}).get(pl.ticker, "neutral")
        pl.score = score_play(pl, ch, reg)
        scored.append(pl)
    scored.sort(key=lambda x: (x.score, x.conviction, x.risk_reward), reverse=True)
    return scored[:top_n] if top_n else scored
