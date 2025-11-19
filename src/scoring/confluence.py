from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


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
    scores: Dict[str, float],
    *,
    weights: Optional[Dict[str, float]] = None,
    default_positioning: float = 50.0
) -> Dict[str, float]:
    """
    Compute a weighted confluence score from individual component scores.
    Returns {"confluence_score": float}
    """

    # Normalize missing positioning like your old version did
    if "positioning_score" not in scores or scores["positioning_score"] is None:
        scores = {**scores, "positioning_score": default_positioning}

    # Default weights (your original tuned version)
    default_weights = {
        "trend_score": 0.32,
        "volatility_score": 0.18,
        "volume_score": 0.18,
        "rs_score": 0.22,
        "positioning_score": 0.10,
    }

    # Allow overrides from config
    w = weights or default_weights

    # Weighted sum
    c = 0.0
    for k, weight in w.items():
        c += weight * scores.get(k, 0.0)

    # Clamp 0 → 100 like your old function
    c = max(0.0, min(100.0, c))

    return {"confluence_score": c}