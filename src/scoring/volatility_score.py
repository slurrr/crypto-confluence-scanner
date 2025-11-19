from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict

from ..data.models import Bar
from ..features.volatility import compute_volatility_features

FeatureDict = Dict[str, float]


@dataclass
class VolatilityScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _inverse_scale_score(x: float, scale: float = 5.0) -> float:
    """
    Simple inverse scoring: higher x -> lower score.

    score = 100 / (1 + x/scale)

    - scale sets how quickly the score drops.
    """
    if x < 0:
        x = 0.0
    return _clamp(100.0 / (1.0 + (x / scale)))


def _contraction_ratio_score(ratio: float) -> float:
    """
    Volatility contraction ratio:

        ratio = recent_atr% / earlier_atr%

    Heuristic scoring:

        <= 0.5  -> 100 (strong contraction)
         1.0    -> ~100
         1.5    -> ~50
        >= 2.0  -> 0
    """
    # Good when <= 1, bad when >> 1
    # We'll treat ratios in [0, 2] -> [100, 0] with clipping
    if ratio <= 0:
        return 100.0
    if ratio >= 2.0:
        return 0.0

    # Map 0..2 -> 1..0, then scale to 0..100
    normalized = (2.0 - ratio) / 2.0  # 0..1
    return _clamp(normalized * 100.0)


def compute_volatility_score(features: FeatureDict) -> VolatilityScoreResult:
    """
    Core Volatility scoring API.

    Input:
        features:
            dict from `compute_volatility_features(...)`, expected keys:
              - volatility_atr_pct_14
              - volatility_bb_width_pct_20
              - volatility_contraction_ratio_60_20

    Output:
        VolatilityScoreResult with:
          - score: 0..100
          - features: dict of raw + component scores
    """
    if not isinstance(features, Mapping) or not features:
        # Not enough data -> neutral-ish
        return VolatilityScoreResult(score=50.0, features={})

    atr_pct = features["volatility_atr_pct_14"]
    bb_width_pct = features["volatility_bb_width_pct_20"]
    contraction_ratio = features["volatility_contraction_ratio_60_20"]

    s_atr = _inverse_scale_score(atr_pct, scale=5.0)
    s_bb = _inverse_scale_score(bb_width_pct, scale=10.0)
    s_contr = _contraction_ratio_score(contraction_ratio)

    # Blend weights (tunable)
    w_atr = 0.30
    w_bb = 0.35
    w_contr = 0.35

    score = w_atr * s_atr + w_bb * s_bb + w_contr * s_contr

    debug_features: Dict[str, float] = {
        # raw
        "volatility_atr_pct_14": atr_pct,
        "volatility_bb_width_pct_20": bb_width_pct,
        "volatility_contraction_ratio_60_20": contraction_ratio,
        # component scores
        "volatility_atr_score": s_atr,
        "volatility_bb_width_score": s_bb,
        "volatility_contraction_ratio_score": s_contr,
    }

    return VolatilityScoreResult(score=_clamp(score), features=debug_features)


def compute_volatility_score_from_bars(
    bars: Sequence[Bar],
) -> VolatilityScoreResult:
    """
    Convenience wrapper for legacy callers.

    Canonical flow in the spec is:
        bars -> features.volatility.compute_volatility_features
             -> scoring.volatility_score.compute_volatility_score

    This helper keeps the older "just give me bars" style alive:
        bars -> compute_volatility_score_from_bars
    """
    vol_features = compute_volatility_features(bars)
    return compute_volatility_score(vol_features)
