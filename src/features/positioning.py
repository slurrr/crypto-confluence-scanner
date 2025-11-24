from __future__ import annotations

from collections.abc import Sequence
from io import DEFAULT_BUFFER_SIZE
from typing import Dict
from unittest.mock import DEFAULT

from ..data.models import Bar, DerivativesMetrics

FeatureDict = Dict[str, float]

DEFAULT_POSITIONING_FEATURES: FeatureDict = {
    "positioning_funding_rate": 0.0,
    "positioning_oi_change_pct": 0.0,
    "has_deriv_data": 0.0,
}

def compute_positioning_features(
    bars: Sequence[Bar],  # unused for now, reserved for future extensions
    derivatives: DerivativesMetrics | None,
) -> FeatureDict:
    """
    Canonical Positioning feature API.

    Returns a *full* stable-schema FeatureDict even if no derivatives data exists.
    """

    # Case 1: No derivatives object at all → return neutral full schema
    if derivatives is None:
        return dict(DEFAULT_POSITIONING_FEATURES)

    # Extract values safely
    funding_rate = derivatives.funding_rate
    oi_change = derivatives.oi_change

    # Case 2: Derivatives exist but all fields are None → treat as "no real data"
    if all(v is None for v in (funding_rate, oi_change)):
        return dict(DEFAULT_POSITIONING_FEATURES)

    # Case 3: Real derivative values exist → build full schema with actual values
    return {
        "positioning_funding_rate": funding_rate or 0.0,
        "positioning_oi_change_pct": oi_change or 0.0,
        "has_deriv_data": 1.0,
    }
