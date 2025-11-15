from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ComponentScores:
    trend: float
    volatility: float
    volume: float
    rs: float
    positioning: float


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
    positioning_score: float | None = None,
) -> ConfluenceScoreResult:
    """
    First-pass Confluence Score including positioning.

    If positioning_score is None, we treat it as neutral (50).
    """
    if positioning_score is None:
        positioning_score = 50.0

    raw_components = {
        "trend": trend_score,
        "volatility": volatility_score,
        "volume": volume_score,
        "rs": rs_score,
        "positioning": positioning_score,
    }

    # Weights (tunable later); small but non-trivial weight on positioning.
    w_trend = 0.32
    w_volatility = 0.18
    w_volume = 0.18
    w_rs = 0.22
    w_positioning = 0.10

    c_score = (
        w_trend * trend_score
        + w_volatility * volatility_score
        + w_volume * volume_score
        + w_rs * rs_score
        + w_positioning * positioning_score
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
            positioning=positioning_score,
        ),
        raw_components=raw_components,
    )
