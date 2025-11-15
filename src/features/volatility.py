from __future__ import annotations

from typing import List

from ..data.models import Bar


def _true_range(prev_close: float, high: float, low: float) -> float:
    """
    True Range for a single bar, given previous close.
    TR = max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close),
    )
    """
    range1 = high - low
    range2 = abs(high - prev_close)
    range3 = abs(low - prev_close)
    return max(range1, range2, range3)


def _atr(bars: List[Bar], period: int = 14) -> float:
    """
    Simple ATR (Average True Range) using Wilder-style smoothing approximation.

    If there are not enough bars, returns 0.0.
    """
    if len(bars) <= period:
        return 0.0

    trs: List[float] = []
    for prev, curr in zip(bars[:-1], bars[1:]):
        tr = _true_range(prev.close, curr.high, curr.low)
        trs.append(tr)

    if len(trs) < period:
        return 0.0

    # First ATR: simple average of first `period` TR values
    atr_prev = sum(trs[:period]) / period

    # Smooth remaining
    for tr in trs[period:]:
        atr_prev = (atr_prev * (period - 1) + tr) / period

    return atr_prev


def compute_atr_percent(bars: List[Bar], period: int = 14) -> float:
    """
    ATR as a percentage of the latest close.

        ATR% = ATR(period) / last_close * 100

    Returns 0.0 if not enough data.
    """
    if len(bars) < period + 1:
        return 0.0

    atr_val = _atr(bars, period=period)
    last_close = bars[-1].close
    if last_close == 0:
        return 0.0

    return atr_val / last_close * 100.0


def compute_bb_width_percent(bars: List[Bar], period: int = 20, std_dev: float = 2.0) -> float:
    """
    Bollinger Band width (upper - lower) as a percentage of the middle band.

        width% = (upper - lower) / middle * 100

    where:
        middle = SMA(close, period)
        upper  = middle + std_dev * std(close over period)
        lower  = middle - std_dev * std(close over period)

    Returns 0.0 if not enough data.
    """
    if len(bars) < period:
        return 0.0

    closes = [b.close for b in bars[-period:]]
    middle = sum(closes) / period
    if middle == 0:
        return 0.0

    mean = middle
    var = sum((c - mean) ** 2 for c in closes) / period
    std = var ** 0.5

    upper = middle + std_dev * std
    lower = middle - std_dev * std

    width = upper - lower
    return width / middle * 100.0


def compute_volatility_contraction_ratio(
    bars: List[Bar],
    window_long: int = 60,
    window_short: int = 20,
) -> float:
    """
    Simple volatility contraction proxy.

    Compares recent ATR% (short window) to earlier ATR% (long window).

        ratio = recent_atr% / earlier_atr%

    Values < 1.0 -> recent volatility is lower than past (contraction).
    Values > 1.0 -> recent volatility is higher than past (expansion).

    Returns 1.0 (neutral) if not enough data or earlier_atr% is ~0.
    """
    if len(bars) < window_long + 1:
        return 1.0

    # Earlier segment: first part of the window_long
    earlier_segment = bars[-(window_long + window_short) : -window_short]
    recent_segment = bars[-(window_short + 1) :]

    earlier_atr_pct = compute_atr_percent(earlier_segment, period=min(14, len(earlier_segment) - 1))
    recent_atr_pct = compute_atr_percent(recent_segment, period=min(14, len(recent_segment) - 1))

    if earlier_atr_pct <= 0:
        return 1.0

    return recent_atr_pct / earlier_atr_pct
