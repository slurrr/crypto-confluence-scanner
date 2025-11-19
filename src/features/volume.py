from __future__ import annotations

from collections.abc import Sequence
from typing import Dict, List

from ..data.models import Bar

FeatureDict = Dict[str, float]


def _volumes(bars: List[Bar]) -> List[float]:
    return [b.volume for b in bars]


def _sma(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_rvol(
    bars: List[Bar],
    lookback: int = 20,
    recent_window: int = 1,
) -> float:
    """
    Compute a simple relative volume (RVOL).

    RVOL = (average volume over last `recent_window` bars) /
           (average volume over previous `lookback` bars)

    Returns 1.0 if not enough data or denominator is ~0.
    """
    vols = _volumes(bars)
    n = len(vols)
    needed = lookback + recent_window
    if n < needed:
        return 1.0

    recent = vols[-recent_window:]
    base = vols[-needed:-recent_window]

    avg_recent = _sma(recent)
    avg_base = _sma(base)

    if avg_base <= 0:
        return 1.0

    return avg_recent / avg_base


def compute_volume_trend_slope(
    bars: List[Bar],
    ma_period: int = 20,
    lookback: int = 10,
) -> float:
    """
    Rough slope of volume over time, based on SMA.

        slope% = (vol_ma_end - vol_ma_start) / vol_ma_start * 100

    Returns 0.0 if not enough data.
    """
    vols = _volumes(bars)
    needed = ma_period + lookback
    if len(vols) < needed:
        return 0.0

    recent = vols[-needed:]
    ma_start = _sma(recent[:ma_period])
    ma_end = _sma(recent[-ma_period:])

    if ma_start <= 0:
        return 0.0

    return (ma_end - ma_start) / ma_start * 100.0


def compute_volume_percentile(
    bars: List[Bar],
    lookback: int = 60,
) -> float:
    """
    Percentile of the latest volume versus the last `lookback` volumes.

    Returns a value in [0.0, 1.0]. 0.9 = last volume is higher than 90% of
    recent history.

    If not enough data, returns 0.5 (neutral).
    """
    vols = _volumes(bars)
    if len(vols) < lookback + 1:
        return 0.5

    window = vols[-(lookback + 1) : -1]
    last = vols[-1]

    if not window:
        return 0.5

    below_or_equal = sum(1 for v in window if v <= last)
    total = len(window)
    return below_or_equal / total if total > 0 else 0.5


def compute_volume_features(bars: Sequence[Bar]) -> FeatureDict:
    """
    Canonical Volume feature API.

    Input:
        - bars: OHLCV history for a single symbol/timeframe (oldest -> newest)

    Output:
        - dict of raw volume features with stable snake_case keys.

    Keys (stable schema):
        - volume_rvol_20_1
        - volume_trend_slope_pct_20_10
        - volume_percentile_60
    """
    # Match the earlier scoring behavior: require some history, or return neutral.
    if len(bars) < 40:
        return {}

    bars_list = list(bars)

    rvol = compute_rvol(bars_list, lookback=20, recent_window=1)
    slope_pct = compute_volume_trend_slope(bars_list, ma_period=20, lookback=10)
    vol_pct = compute_volume_percentile(bars_list, lookback=60)

    return {
        "volume_rvol_20_1": rvol,
        "volume_trend_slope_pct_20_10": slope_pct,
        "volume_percentile_60": vol_pct,
    }
