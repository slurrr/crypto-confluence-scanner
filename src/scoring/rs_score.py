from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict

from ..data.models import Bar
from ..features.relative_strength import compute_rs_features

FeatureDict = Dict[str, float]


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
            dict from `compute_rs_features(...)`, expected keys:
              - rs_ret_20_pct
              - rs_ret_60_pct
              - rs_ret_120_pct

    Output:
        RelativeStrengthScoreResult with:
          - score: 0..100
          - features: dict of raw + component scores
    """
    if not features:
        # Too little data; neutral-ish, empty features.
        return RelativeStrengthScoreResult(score=50.0, features={})

    ret_20 = features["rs_ret_20_pct"]
    ret_60 = features["rs_ret_60_pct"]
    ret_120 = features["rs_ret_120_pct"]

    s_20 = _return_score(ret_20)
    s_60 = _return_score(ret_60)
    s_120 = _return_score(ret_120)

    # You can tune these weights later; for now:
    # slightly more emphasis on 3M/6M.
    w_20 = 0.25
    w_60 = 0.35
    w_120 = 0.40

    score = w_20 * s_20 + w_60 * s_60 + w_120 * s_120

    debug_features: Dict[str, float] = {
        # raw returns
        "rs_ret_20_pct": ret_20,
        "rs_ret_60_pct": ret_60,
        "rs_ret_120_pct": ret_120,
        # component scores
        "rs_ret_20_score": s_20,
        "rs_ret_60_score": s_60,
        "rs_ret_120_score": s_120,
    }
    #print(debug_features)
    return RelativeStrengthScoreResult(score=_clamp(score), features=debug_features)


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
