from __future__ import annotations

from collections.abc import Sequence
from typing import Dict

from ..data.models import Bar, DerivativesMetrics

FeatureDict = Dict[str, float]


def compute_positioning_features(
    bars: Sequence[Bar],  # unused for now, reserved for future extensions
    derivatives: DerivativesMetrics | None,
) -> FeatureDict:
    """
    Canonical Positioning feature API.

    Input:
        - bars: OHLCV history for a single symbol/timeframe (oldest -> newest).
                Currently unused for v1, but included to keep the standard
                feature API shape.
        - derivatives: DerivativesMetrics for this symbol (may be None).

    Output:
        - dict of raw positioning features with stable snake_case keys.

    Keys (stable schema, v1):
        - positioning_funding_rate        : float (raw funding_rate)
        - positioning_oi_change_pct       : float (raw oi_change %, same units
                                                as DerivativesMetrics)
        - positioning_has_derivatives_data: float (0.0 or 1.0) for convenience
    """
    if derivatives is None:
        return {}

    has_any = any(
        v is not None
        for v in (
            derivatives.funding_rate,
            derivatives.open_interest,
            derivatives.funding_z,
            derivatives.oi_change,
        )
    )

    if not has_any:
        return {}

    funding_rate = derivatives.funding_rate or 0.0
    oi_change = derivatives.oi_change or 0.0

    return {
        "positioning_funding_rate": funding_rate,
        "positioning_oi_change_pct": oi_change,
        "positioning_has_derivatives_data": 1.0,
    }
