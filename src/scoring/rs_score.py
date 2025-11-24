from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict

from attr import has

from ..data.models import Bar
from ..features.relative_strength import compute_rs_features

FeatureDict = Dict[str, float]

RANK_WEIGHTS: Dict[str, float] = {
    # Slightly overweight recent (20) while keeping 60/120 in the mix.
    "rs_20_rank_pct": 0.45,
    "rs_60_rank_pct": 0.35,
    "rs_120_rank_pct": 0.20,
}

# Fallback weights when only raw returns are available.
RETURN_WEIGHTS: Dict[str, float] = {
    "rs_ret_20_pct": 0.45,
    "rs_ret_60_pct": 0.35,
    "rs_ret_120_pct": 0.20,
}


@dataclass
class RelativeStrengthScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _return_score(
    ret_pct: float,
    neg_cap: float = -50.0,
    pos_cap: float = 150.0,
) -> float:
    """
    Map a raw % return to a 0..100 score.

    - returns <= neg_cap  -> 0
    - returns >= pos_cap  -> 100
    - linearly scaled in between

    This is a simple, tunable proxy; we just want a stable scale
    for now.
    """
    if ret_pct <= neg_cap:
        return 0.0
    if ret_pct >= pos_cap:
        return 100.0

    span = pos_cap - neg_cap
    normalized = (ret_pct - neg_cap) / span  # 0..1
    return _clamp(normalized * 100.0)


def compute_relative_strength_score(
    features: FeatureDict,
) -> RelativeStrengthScoreResult:
    """
    Core Relative Strength scoring API.

    Input:
        features:
            dict from `compute_rs_features(...)`.
            Preferred keys (cross-sectional):
              - rs_20_rank_pct
              - rs_60_rank_pct
              - rs_120_rank_pct
            Fallback keys (single-asset):
              - rs_ret_20_pct
              - rs_ret_60_pct
              - rs_ret_120_pct

    Output:
        RelativeStrengthScoreResult with:
          - score: 0..100
          - features: dict of raw + component scores
    """
    #Debugging Legacy callers
    if not isinstance(features, Mapping):
        raise TypeError(
            f"compute_rs_score expected FeatureDict, got {type(features)}. "
            "Did you mean to call compute_trend_score_from_bars(bars)?"
        )
    
    debug_features: Dict[str, float] = {}

    has_rs_data = float(features.get("has_rs_data", 0.0))
    if not has_rs_data:
        default_score = 50.0  # middle of 0..100, adjust if you prefer
        debug_features = dict(features)
        debug_features["rs_score_source"] = "default"
        return RelativeStrengthScoreResult(score=default_score, features=debug_features)

    # First preference: cross-sectional percentile ranks.
    num = 0.0
    den = 0.0
    for key, weight in RANK_WEIGHTS.items():
        val = features.get(key)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        num += weight * v
        den += weight
        debug_features[key] = v

    source = "percentile" if den > 0 else "returns_fallback"

    # Fallback: map raw returns to scores if no percentile ranks available.
    if den == 0.0:
        for key, weight in RETURN_WEIGHTS.items():
            val = features.get(key)
            if val is None:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            comp = _return_score(v)
            num += weight * comp
            den += weight
            debug_features[key] = v
            debug_features[f"{key}_score"] = comp

    # Preserve raw returns in debug output if available.
    for key in RETURN_WEIGHTS:
        if key in features and key not in debug_features:
            try:
                debug_features[key] = float(features[key])
            except (TypeError, ValueError):
                pass

    if den == 0.0:
        # Still nothing usable; keep neutral.
        return RelativeStrengthScoreResult(score=50.0, features=debug_features)

    score = _clamp(num / den)
    debug_features["rs_score_source"] = source
    return RelativeStrengthScoreResult(score=score, features=debug_features)


def compute_relative_strength_score_from_bars(
    bars: Sequence[Bar],
) -> RelativeStrengthScoreResult:
    """
    Convenience wrapper for legacy callers.

    Canonical flow in the spec is:
        bars -> features.relative_strength.compute_rs_features
             -> scoring.rs_score.compute_relative_strength_score

    This helper keeps the older "just give me bars" calling style alive:
        bars -> compute_relative_strength_score_from_bars
    """
    rs_features = compute_rs_features(bars, universe_returns=None)
    return compute_relative_strength_score(rs_features)
