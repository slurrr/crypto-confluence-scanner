from __future__ import annotations
from typing import Dict, List, Sequence

from ..data.models import Bar

FeatureDict = Dict[str, float]

# Require at least this many bars for "real" trend signals (MA50 + slope lookback).
MIN_TREND_BARS = 60


def _take_last(values: List[float], n: int) -> List[float]:
    """Return the last n values (or all if list shorter)."""
    if n <= 0:
        return []
    return values[-n:]


def _closes(bars: List[Bar]) -> List[float]:
    """Extract closing prices from bars."""
    return [b.close for b in bars]


def _sma(values: List[float]) -> float:
    """Simple moving average of a non-empty list."""
    return sum(values) / len(values)


def compute_ma_alignment(bars: List[Bar], short_period: int, long_period: int) -> float:
    """
    MA alignment signal for trend direction.

    Returns:
        +1.0 if short MA > long MA (bullish),
        -1.0 if short MA < long MA (bearish),
         0.0 if we don't have enough data or they're effectively equal.
    """
    closes = _closes(bars)
    if len(closes) < max(short_period, long_period):
        return 0.0

    short_ma = _sma(_take_last(closes, short_period))
    long_ma = _sma(_take_last(closes, long_period))

    eps = 1e-8
    if abs(short_ma - long_ma) <= eps:
        return 0.0
    return 1.0 if short_ma > long_ma else -1.0


def compute_trend_persistence(bars: List[Bar], lookback: int = 20) -> float:
    """
    Fraction of the last `lookback` bars that closed above the previous close.

    Rough proxy for "how often has this been grinding up recently?"
    Returns a value between 0.0 and 1.0. If not enough data, returns 0.5 (neutral).
    """
    if len(bars) < lookback + 1:
        # Not enough history; return neutral-ish
        return 0.5

    recent = bars[-(lookback + 1) :]
    up_days = 0
    total = 0

    for prev, curr in zip(recent[:-1], recent[1:]):
        total += 1
        if curr.close > prev.close:
            up_days += 1

    if total == 0:
        return 0.5

    return up_days / total


def compute_distance_from_ma(bars: List[Bar], ma_period: int = 50) -> float:
    """
    Distance of last close from its MA, as a percentage of the MA.

    Positive when price is above the MA, negative when below.

        distance% = (close - MA) / MA * 100

    Returns 0.0 if not enough data.
    """
    closes = _closes(bars)
    if len(closes) < ma_period:
        return 0.0

    ma = _sma(_take_last(closes, ma_period))
    if ma == 0:
        return 0.0

    last_close = closes[-1]
    return (last_close - ma) / ma * 100.0


def compute_ma_slope_percent(
    bars: List[Bar],
    ma_period: int = 50,
    lookback: int = 5,
) -> float:
    """
    Slope of a moving average over the last `lookback` bars, as a percentage.

    Rough idea:
        slope% = (MA_now - MA_lookback) / MA_lookback * 100

    Positive => MA rising, negative => MA falling.
    Returns 0.0 if not enough data.
    """
    closes = _closes(bars)
    needed = ma_period + lookback
    if len(closes) < needed:
        return 0.0

    recent = closes[-needed:]
    # MA at "start" of lookback window
    ma_start = _sma(recent[:ma_period])
    # MA at "end" of lookback window
    ma_end = _sma(recent[-ma_period:])

    if ma_start == 0:
        return 0.0

    return (ma_end - ma_start) / ma_start * 100.0


def compute_trend_features(bars: Sequence[Bar]) -> FeatureDict:
    """
    Canonical Trend feature API.

    Input:
        - bars: OHLCV history for a single symbol/timeframe (oldest -> newest)

    Output:
        - dict of raw trend features with stable snake_case keys.

    Keys (stable schema):
        - trend_ma_alignment        : float in {-1.0, 0.0, +1.0}
        - trend_persistence         : float in [0.0, 1.0]
        - trend_distance_from_ma_pct: float, signed % from MA
        - trend_ma_slope_pct        : float, approx % change of MA over lookback
    """
    bars_list = list(bars)
    if len(bars_list) < MIN_TREND_BARS:
        # Not enough history -> neutral defaults with explicit has_data flag.
        return {
            "trend_ma_alignment": 0.0,
            "trend_persistence": 0.5,
            "trend_distance_from_ma_pct": 0.0,
            "trend_ma_slope_pct": 0.0,
            "has_trend_data": 0.0,
        }

    ma_align = compute_ma_alignment(bars_list, short_period=20, long_period=50)
    persistence = compute_trend_persistence(bars_list, lookback=20)
    dist_pct = compute_distance_from_ma(bars_list, ma_period=50)
    slope_pct = compute_ma_slope_percent(bars_list, ma_period=50, lookback=5)

    return {
        "trend_ma_alignment": ma_align,
        "trend_persistence": persistence,
        "trend_distance_from_ma_pct": dist_pct,
        "trend_ma_slope_pct": slope_pct,
        "has_trend_data": 1.0,
    }
