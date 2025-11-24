from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

#from features.volume import FeatureDict
from collections.abc import Mapping

from ..data.models import Bar
from ..features.trend import compute_trend_features

FeatureDict = Dict[str, float]

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
    # -1 -> 0.0
    # 1  -> 100.0

def _persistence_score(persistence: float) -> float:
    """
    persistence in [0, 1] -> [0, 100]
    """
    return _clamp(persistence * 100.0)
    #0.45 -> 45.0

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
#10.89 -> ~45.55


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
    # -1.529 -> ~20.0

def compute_trend_score(features: FeatureDict) -> TrendScoreResult:
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
    
    # Pull with safe defaults in case upstream didn't populate everything
    ma_align = float(features.get("trend_ma_alignment", 0.0))
    persistence = float(features.get("trend_persistence", 0.5))
    dist_pct = float(features.get("trend_distance_from_ma_pct", 0.0))
    slope_pct = float(features.get("trend_ma_slope_pct", 0.0))
    has_trend_data = float(
        features.get("has_trend_data", features.get("has_trend__data", 0.0))
    )

    # If we *don't* have real trend data, emit a neutral trend score.
    # Confluence confidence can then look at has_trend__data to down-weight this module.
    if not has_trend_data:
        default_score = 50.0  # middle of 0..100, adjust if you prefer
        debug_features: Dict[str, float] = {
            "trend_ma_alignment": ma_align,
            "trend_persistence": persistence,
            "trend_distance_from_ma_pct": dist_pct,
            "trend_ma_slope_pct": slope_pct,
            "has_trend_data": has_trend_data,
        }
        return TrendScoreResult(score=default_score, features=debug_features)

    # --- Component scores ---
    s_align = _ma_alignment_score(ma_align)
    # -1 -> 0
    s_persist = _persistence_score(persistence)
    # 0.45 -> 45.0
    s_dist = _extension_score(dist_pct, ideal_band=5.0)
    # 10.89 -> ~45.55
    s_slope = _ma_slope_score(slope_pct, max_abs=5.0)
    # -1.529 -> ~20.0

    # --- Weighted blend (weights can be tuned later) ---
    w_align = 0.35
    w_persist = 0.30
    w_dist = 0.20
    w_slope = 0.15

    score = (
        w_align * s_align
        # 0.35 * 0 = 0
        + w_persist * s_persist
        # 0.30 * 45.0 = 13.5
        + w_dist * s_dist
        # 0.20 * 45.55 = 9.11
        + w_slope * s_slope
        # 0.15 * 20.0 = 3.0
        # score ~= 25.61
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
    #print(debug_features)
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
