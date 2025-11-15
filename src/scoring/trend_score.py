from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..data.models import Bar
from ..features.trend import (
    compute_ma_alignment,
    compute_trend_persistence,
    compute_distance_from_ma,
    compute_ma_slope_percent,
)


@dataclass
class TrendScoreResult:
    score: float
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


def compute_trend_score(bars: List[Bar]) -> TrendScoreResult:
    """
    Compute a first-pass Trend Score from basic MA-based features.

    This is intentionally simple and will be refined later using your
    more detailed scoring research. For now:

        trend_score = weighted sum of:
            - MA alignment
            - trend persistence
            - distance from MA
            - MA slope

    Returns:
        TrendScoreResult with:
            - score: 0..100
            - features: dict of raw + component scores
    """
    if len(bars) < 60:
        # Not enough history for robust signals; neutral.
        return TrendScoreResult(score=50.0, features={})

    # --- Raw features ---
    ma_align = compute_ma_alignment(bars, short_period=20, long_period=50)
    persistence = compute_trend_persistence(bars, lookback=20)
    dist_pct = compute_distance_from_ma(bars, ma_period=50)
    slope_pct = compute_ma_slope_percent(bars, ma_period=50, lookback=5)

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

    features = {
        "ma_align_raw": ma_align,
        "ma_align_score": s_align,
        "trend_persistence_raw": persistence,
        "trend_persistence_score": s_persist,
        "distance_from_ma_pct_raw": dist_pct,
        "distance_from_ma_score": s_dist,
        "ma_slope_pct_raw": slope_pct,
        "ma_slope_score": s_slope,
    }

    return TrendScoreResult(score=_clamp(score), features=features)
