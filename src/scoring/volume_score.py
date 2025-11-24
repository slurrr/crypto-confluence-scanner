from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict

from ..data.models import Bar
from ..features.volume import compute_volume_features

FeatureDict = Dict[str, float]


@dataclass
class VolumeScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _rvol_score(
    rvol: float,
    ideal_low: float = 1.5,
    ideal_high: float = 3.0,
) -> float:
    """
    Score RVOL for breakout-type setups.

    - rvol < 1.0 : low interest -> score drops
    - rvol ~ 1.5-3.0 : sweet spot -> high scores
    - rvol >> 3.0 : still decent but taper off to avoid parabolic risk
    """
    if rvol <= 0:
        return 0.0

    # Under 1: linear from 0..1 -> 0..60
    if rvol < 1.0:
        return _clamp(rvol * 60.0, 0.0, 60.0)

    # Sweet spot 1.0..ideal_low -> ramp 60..80
    if rvol < ideal_low:
        t = (rvol - 1.0) / (ideal_low - 1.0)  # 0..1
        return 60.0 + t * 20.0  # 60..80

    # Sweet spot ideal_low..ideal_high -> 80..100
    if rvol <= ideal_high:
        t = (rvol - ideal_low) / (ideal_high - ideal_low)  # 0..1
        return 80.0 + t * 20.0  # 80..100

    # Above ideal_high: gradually decay from 100 down toward 70
    # as rvol goes from ideal_high..(ideal_high+4)
    extra = rvol - ideal_high
    if extra >= 4.0:
        return 70.0
    return 100.0 - (extra / 4.0) * 30.0  # 100..70


def _volume_trend_score(slope_pct: float, max_abs: float = 20.0) -> float:
    """
    Favor rising volume, mildly penalize falling.

    Map slope_pct in [-max_abs, +max_abs] to [0, 100].
    """
    s = max(-max_abs, min(max_abs, slope_pct))
    normalized = (s + max_abs) / (2 * max_abs)  # 0..1
    return normalized * 100.0


def _volume_percentile_score(pct: float) -> float:
    """
    pct in [0,1] -> [0,100]
    """
    return _clamp(pct * 100.0)


def compute_volume_score(features: FeatureDict) -> VolumeScoreResult:
    """
    Core Volume scoring API.

    Input:
        features:
            dict from `compute_volume_features(...)`, expected keys:
              - volume_rvol_20_1
              - volume_trend_slope_pct_20_10
              - volume_percentile_60

    Output:
        VolumeScoreResult with:
          - score: 0..100
          - features: dict of raw + component scores
    """
    if not isinstance(features, Mapping) or not features:
        raise TypeError(
            f"compute_volume_score expected FeatureDict, got {type(features)}. "
            "Did you mean to call compute_trend_score_from_bars(bars)?"
        )

    rvol = float(features.get("volume_rvol_20_1", 0.0))
    slope_pct = float(features.get("volume_trend_slope_pct_20_10", 0.0))    
    vol_pct = float(features.get("volume_percentile_60", 0.5))
    has_volume_data = float(
        features.get("has_volume_data", features.get("has_volu_data", 0.0))
    )

    # If we *don't* have real data, emit a neutral score.
    if not has_volume_data:
        default_score = 50.0  # neutral default
        debug_features: Dict[str, float] = {
            "volume_rvol_20_1": rvol,
            "volume_trend_slope_pct_20_10": slope_pct,
            "volume_percentile_60": vol_pct,
            "has_volume_data": has_volume_data,
        }
        return VolumeScoreResult(score=default_score, features=debug_features)


    s_rvol = _rvol_score(rvol, ideal_low=1.5, ideal_high=3.0)
    s_slope = _volume_trend_score(slope_pct, max_abs=20.0)
    s_pct = _volume_percentile_score(vol_pct)

    # Blend weights (tunable later)
    w_rvol = 0.45
    w_slope = 0.25
    w_pct = 0.30

    score = w_rvol * s_rvol + w_slope * s_slope + w_pct * s_pct
    
    debug_features: Dict[str, float] = {
        # raw
        "volume_rvol_20_1": rvol,
        "volume_trend_slope_pct_20_10": slope_pct,
        "volume_percentile_60": vol_pct,
        # component scores
        "volume_rvol_score": s_rvol,
        "volume_trend_slope_score": s_slope,
        "volume_percentile_score": s_pct,
        "has_volume_data": has_volume_data,
    }
    #print(debug_features)
    return VolumeScoreResult(score=_clamp(score), features=debug_features)


def compute_volume_score_from_bars(
    bars: Sequence[Bar],
) -> VolumeScoreResult:
    """
    Convenience wrapper for legacy callers.

    Canonical flow:
        bars -> features.volume.compute_volume_features
             -> scoring.volume_score.compute_volume_score

    This helper keeps the older "just give me bars" calling style alive:
        bars -> compute_volume_score_from_bars
    """
    vol_features = compute_volume_features(bars)
    return compute_volume_score(vol_features)
