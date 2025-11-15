from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ComponentScores:
    trend: float
    volatility: float
    volume: float
    rs: float


@dataclass
class ConfluenceScoreResult:
    symbol: str
    timeframe: str
    confluence_score: float
    components: ComponentScores
    raw_components: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def compute_confluence_score(
    symbol: str,
    timeframe: str,
    trend_score: float,
    volatility_score: float,
    volume_score: float,
    rs_score: float,
) -> ConfluenceScoreResult:
    """
    First-pass Confluence Score.

    Simple weighted blend of component scores, all assumed in [0,100].

    You can later:
      - adjust weights,
      - condition on market regime,
      - add positioning / funding / OI as extra components.
    """
    # Weights (tunable later)
    w_trend = 0.35
    w_volatility = 0.20
    w_volume = 0.20
    w_rs = 0.25

    raw_components = {
        "trend": trend_score,
        "volatility": volatility_score,
        "volume": volume_score,
        "rs": rs_score,
    }

    c_score = (
        w_trend * trend_score
        + w_volatility * volatility_score
        + w_volume * volume_score
        + w_rs * rs_score
    )

    return ConfluenceScoreResult(
        symbol=symbol,
        timeframe=timeframe,
        confluence_score=_clamp(c_score),
        components=ComponentScores(
            trend=trend_score,
            volatility=volatility_score,
            volume=volume_score,
            rs=rs_score,
        ),
        raw_components=raw_components,
    )
