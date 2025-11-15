from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from ..data.models import DerivativesMetrics


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


def compute_positioning_score(deriv: DerivativesMetrics) -> PositioningScoreResult:
    """
    First-pass Positioning / Funding / OI score.

    If we have no derivatives data at all, return a neutral 50 with
    empty features so the rest of the system can gracefully ignore it.

    Otherwise we blend:
      - funding_crowding_score (prefer balanced/uncrowded)
      - oi_build_up_score (prefer measured build-up over exits)
    """
    has_any = any(
        v is not None
        for v in (
            deriv.funding_rate,
            deriv.open_interest,
            deriv.funding_z,
            deriv.oi_change,
        )
    )

    if not has_any:
        return PositioningScoreResult(score=50.0, features={})

    funding_rate = deriv.funding_rate or 0.0
    oi_change = deriv.oi_change or 0.0

    s_funding = _funding_crowding_score(funding_rate)
    s_oi = _oi_build_up_score(oi_change)

    # Blend weights (tunable later)
    w_funding = 0.6
    w_oi = 0.4

    score = w_funding * s_funding + w_oi * s_oi

    features: Dict[str, float] = {
        "funding_rate_raw": funding_rate,
        "funding_crowding_score": s_funding,
        "oi_change_raw": oi_change,
        "oi_build_up_score": s_oi,
    }

    return PositioningScoreResult(score=_clamp(score), features=features)
