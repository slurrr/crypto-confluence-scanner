from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict

from attr import has

from ..data.models import Bar, DerivativesMetrics
from ..features.positioning import compute_positioning_features

FeatureDict = Dict[str, float]


@dataclass
class PositioningScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _funding_crowding_score(funding_rate: float) -> float:
    """
    Map perp funding rate to a 0–100 crowding score.

    - funding_rate near 0 -> score ~100 (uncrowded)
    - larger |funding_rate| -> lower score (more crowded)
    - |funding_rate| >= max_abs -> score bottoms near 10
    """
    abs_fr = abs(funding_rate or 0.0)

    # This is the "this is definitely crowded" threshold.
    # 0.0005 = 0.05% per funding interval; tweak as you like.
    max_abs = 0.0005

    if abs_fr <= 0.0:
        return 100.0

    # Cap at max_abs so extreme outliers don't matter more than "very crowded"
    if abs_fr >= max_abs:
        return 10.0

    # Linearly interpolate from 100 (at 0) down to 10 (at max_abs)
    ratio = abs_fr / max_abs  # 0 → 1
    score = 100.0 - 90.0 * ratio  # 100 → 10
    return max(0.0, min(100.0, score))


def _oi_build_up_score(oi_change: float) -> float:
    """
    Score open interest change.

    Positive change (positions building) -> higher score.
    Large negative change (positions exiting) -> lower score.

    We treat oi_change as % change over some window (you'll define
    that when wiring real data).
    """
    # Clamp change to [-100%, +100%] to avoid insane values breaking scale.
    c = max(-100.0, min(100.0, oi_change))

    # Map -100..+100 -> 0..100 (linear for now)
    normalized = (c + 100.0) / 200.0
    return _clamp(normalized * 100.0)


def compute_positioning_score(features: FeatureDict) -> PositioningScoreResult:
    """
    Core Positioning scoring API.

    Input:
        features:
            dict from `compute_positioning_features(...)`, expected keys:
              - positioning_funding_rate
              - positioning_oi_change_pct
              - positioning_has_derivatives_data

    Output:
        PositioningScoreResult with:
          - score: 0..100
          - features: dict of raw + component scores
    """
    #Debugging Legacy callers
    if not isinstance(features, Mapping):
        raise TypeError(
            f"compute_positioning_score expected FeatureDict, got {type(features)}. "
            "Did you mean to call compute_trend_score_from_bars(bars)?"
        )

    funding_rate = features.get("positioning_funding_rate", 0.0)
    oi_change = features.get("positioning_oi_change_pct", 0.0)
    has_deriv_data = features.get("has_deriv_data", 0.0)   

    # Case: No real derivatives → emit neutral score
    if not has_deriv_data:
        neutral_score = 50.0
        debug_features = {
            "positioning_funding_rate": funding_rate,
            "positioning_oi_change_pct": oi_change,
            "positioning_funding_crowding_score": 50.0,
            "positioning_oi_build_up_score": 50.0,
            "has_deriv_data": has_deriv_data,   
        }
        return PositioningScoreResult(score=neutral_score, features=debug_features)

    # Real data path    
    s_funding = _funding_crowding_score(funding_rate)
    s_oi = _oi_build_up_score(oi_change)

    # Blend weights (tunable later)
    w_funding = 0.6
    w_oi = 0.4

    score = w_funding * s_funding + w_oi * s_oi

    debug_features: Dict[str, float] = {
        # raw inputs
        "positioning_funding_rate": funding_rate,
        "positioning_oi_change_pct": oi_change,
        # component scores
        "positioning_funding_crowding_score": s_funding,
        "positioning_oi_build_up_score": s_oi,
    }
    #print(debug_features)

    return PositioningScoreResult(score=_clamp(score), features=debug_features)


def compute_positioning_score_from_bars_and_derivatives(
    bars: Sequence[Bar],
    derivatives: DerivativesMetrics | None,
) -> PositioningScoreResult:
    """
    Convenience wrapper for legacy / simpler callers.

    Canonical flow in the spec is:
        (bars, derivatives)
          -> features.positioning.compute_positioning_features
          -> scoring.positioning_score.compute_positioning_score
    """
    pos_features = compute_positioning_features(bars, derivatives)
    return compute_positioning_score(pos_features)


def compute_positioning_score_from_derivatives(
    derivatives: DerivativesMetrics | None,
) -> PositioningScoreResult:
    """
    Extra convenience wrapper if callers don't care about bars at all yet.
    """
    # empty tuple for bars; positioning features v1 ignore bars anyway
    pos_features = compute_positioning_features((), derivatives)
    return compute_positioning_score(pos_features)
