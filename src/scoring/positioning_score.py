from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict

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
    Simple 'crowding' score from funding.

    We don't assume a specific unit. Heuristic:
      - best when funding ~ 0 (balanced)
      - penalize large |funding| as crowded
    """

    # Treat funding_rate as "per interval" decimal; typical ranges are tiny.
    # We'll work on absolute value.
    f_abs = abs(funding_rate)

    # Below 0.01% -> basically flat -> ~100
    # 0.01%..0.05% -> gently down toward 60
    # 0.05%..0.20% -> down toward 20
    # >=0.20% -> capped at 10
    if f_abs <= 0.0001:  # 0.01%
        return 100.0
    if f_abs <= 0.0005:  # 0.05%
        # 0.0001..0.0005 -> 100..60
        t = (f_abs - 0.0001) / (0.0005 - 0.0001)
        return 100.0 - t * 40.0
    if f_abs <= 0.002:  # 0.20%
        # 0.0005..0.002 -> 60..20
        t = (f_abs - 0.0005) / (0.002 - 0.0005)
        return 60.0 - t * 40.0

    return 10.0


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
    if not isinstance(features, Mapping) or not features:
        return PositioningScoreResult(score=50.0, features={})

    funding_rate = features.get("positioning_funding_rate", 0.0)
    oi_change = features.get("positioning_oi_change_pct", 0.0)

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
