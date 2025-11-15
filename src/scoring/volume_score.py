from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..data.models import Bar
from ..features.volume import (
    compute_rvol,
    compute_volume_trend_slope,
    compute_volume_percentile,
)


@dataclass
class VolumeScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _rvol_score(rvol: float, ideal_low: float = 1.5, ideal_high: float = 3.0) -> float:
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


def compute_volume_score(bars: List[Bar]) -> VolumeScoreResult:
    """
    Compute a first-pass Volume Score from:

        - RVOL (recent vs base)
        - Volume trend slope
        - Volume percentile

    This is breakout-biased: more volume and increasing volume get rewarded.
    """
    if len(bars) < 40:
        # Not enough data for reliable stats; neutral-ish.
        return VolumeScoreResult(score=50.0, features={})

    rvol = compute_rvol(bars, lookback=20, recent_window=1)
    slope_pct = compute_volume_trend_slope(bars, ma_period=20, lookback=10)
    vol_pct = compute_volume_percentile(bars, lookback=60)

    s_rvol = _rvol_score(rvol, ideal_low=1.5, ideal_high=3.0)
    s_slope = _volume_trend_score(slope_pct, max_abs=20.0)
    s_pct = _volume_percentile_score(vol_pct)

    # Blend weights (tunable later)
    w_rvol = 0.45
    w_slope = 0.25
    w_pct = 0.30

    score = w_rvol * s_rvol + w_slope * s_slope + w_pct * s_pct

    features = {
        "rvol_raw": rvol,
        "rvol_score": s_rvol,
        "volume_trend_slope_pct_raw": slope_pct,
        "volume_trend_slope_score": s_slope,
        "volume_percentile_raw": vol_pct,
        "volume_percentile_score": s_pct,
    }

    return VolumeScoreResult(score=_clamp(score), features=features)
