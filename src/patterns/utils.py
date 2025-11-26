from __future__ import annotations

from collections.abc import Sequence
from typing import Iterable, Optional

from ..data.models import Bar


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def pct_change(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return (new - old) / old * 100.0


def simple_moving_average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def exponential_moving_average(values: Sequence[float], period: int) -> float:
    """
    Lightweight EMA for small sequences used in pattern checks.
    Returns 0.0 if not enough data.
    """
    if period <= 0 or len(values) < period:
        return 0.0

    k = 2.0 / (period + 1)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = v * k + ema_val * (1 - k)
    return ema_val


def highest_high(bars: Sequence[Bar], lookback: int) -> Optional[float]:
    """Highest high over the last `lookback` bars (excluding the current bar)."""
    if lookback <= 0 or len(bars) < lookback + 1:
        return None
    window = bars[-(lookback + 1) : -1]
    if not window:
        return None
    return max(b.high for b in window)


def lowest_low(bars: Sequence[Bar], lookback: int) -> Optional[float]:
    """Lowest low over the last `lookback` bars (excluding the current bar)."""
    if lookback <= 0 or len(bars) < lookback + 1:
        return None
    window = bars[-(lookback + 1) : -1]
    if not window:
        return None
    return min(b.low for b in window)


def recent_closes(bars: Sequence[Bar], lookback: int) -> list[float]:
    return [b.close for b in bars[-lookback:]]


def percentile_rank(value: float, population: Iterable[float]) -> float:
    """
    Return percentile rank of `value` within `population` on a 0-100 scale.
    """
    vals = [v for v in population if v is not None]
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    below = sum(1 for v in sorted_vals if v <= value)
    return clamp((below / len(sorted_vals)) * 100.0, 0.0, 100.0)
