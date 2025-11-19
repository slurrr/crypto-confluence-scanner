from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from ..data.models import Bar
from ..features.trend import compute_trend_features
from collections.abc import Mapping

@dataclass
class TrendScoreResult:
    score: float
    # Includes raw + component scores used for debugging / reports
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _ma_alignment_score(alignment: float) -> float:
    """
    alignment is -1, 0, or +1.

    Map:
        -1 ->   0
         0 ->  50
        +1 -> 100
    """
    return (alignment + 1.0) * 50.0


def _persistence_score(persistence: float) -> float:
    """
    persistence in [0, 1] -> [0, 100]
    """
    return _clamp(persistence * 100.0)


def _extension_score(distance_pct: float, ideal_band: float = 5.0) -> float:
    """
    Penalize being too far from the MA.

    distance_pct is signed (% above/below MA). We care about |distance|.

    Within +/- ideal_band% -> close to 100
    Further away -> linearly decays toward 0.
    """
    dist = abs(distance_pct)
    if dist <= ideal_band:
        return 100.0
    # Each extra 1% beyond ideal_band knocks off 5 pts (tunable)
    extra = dist - ideal_band
    return _clamp(100.0 - extra * 5.0)


def _ma_slope_score(slope_pct: float, max_abs: float = 5.0) -> float:
    """
    Favor rising MAs, penalize falling.

    slope_pct is roughly % change of MA over lookback period.

    Clamp to [-max_abs, max_abs], then map:
        -max_abs -> 0
         0       -> 50
        +max_abs -> 100
    """
    s = max(-max_abs, min(max_abs, slope_pct))
    normalized = (s + max_abs) / (2 * max_abs)  # 0..1
    return normalized * 100.0


def compute_trend_score(features: Dict[str, float]) -> TrendScoreResult:
    """
    Core Trend scoring API.

    Input:
        features:
            dict from `compute_trend_features(...)`, expected keys:
              - trend_ma_alignment
              - trend_persistence
              - trend_distance_from_ma_pct
              - trend_ma_slope_pct

    Output:
        TrendScoreResult with:
          - score: 0..100
          - features: dict of raw + component scores
    """
    #Debugging Legacy callers
    if not isinstance(features, Mapping):
        raise TypeError(
            f"compute_trend_score expected FeatureDict, got {type(features)}. "
            "Did you mean to call compute_trend_score_from_bars(bars)?"
        )
    
    # If features are missing (e.g., not enough bars), return neutral.
    if not features:
        return TrendScoreResult(score=50.0, features={})

    ma_align = features["trend_ma_alignment"]
    persistence = features["trend_persistence"]
    dist_pct = features["trend_distance_from_ma_pct"]
    slope_pct = features["trend_ma_slope_pct"]

    # --- Component scores ---
    s_align = _ma_alignment_score(ma_align)
    s_persist = _persistence_score(persistence)
    s_dist = _extension_score(dist_pct, ideal_band=5.0)
    s_slope = _ma_slope_score(slope_pct, max_abs=5.0)

    # --- Weighted blend (weights can be tuned later) ---
    w_align = 0.35
    w_persist = 0.30
    w_dist = 0.20
    w_slope = 0.15

    score = (
        w_align * s_align
        + w_persist * s_persist
        + w_dist * s_dist
        + w_slope * s_slope
    )

    debug_features: Dict[str, float] = {
        # raw inputs
        "trend_ma_alignment": ma_align,
        "trend_persistence": persistence,
        "trend_distance_from_ma_pct": dist_pct,
        "trend_ma_slope_pct": slope_pct,
        # component scores
        "trend_ma_alignment_score": s_align,
        "trend_persistence_score": s_persist,
        "trend_distance_from_ma_score": s_dist,
        "trend_ma_slope_score": s_slope,
    }

    return TrendScoreResult(score=_clamp(score), features=debug_features)


def compute_trend_score_from_bars(bars: List[Bar]) -> TrendScoreResult:
    """
    Convenience wrapper for legacy callers.

    Canonical flow in the spec is:
        bars -> features.trend.compute_trend_features -> scoring.trend_score.compute_trend_score

    This helper keeps the old "just give me bars" calling style alive:
        bars -> compute_trend_score_from_bars
    """
    trend_features = compute_trend_features(bars)
    return compute_trend_score(trend_features)
