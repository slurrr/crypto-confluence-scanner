from __future__ import annotations

from typing import Dict, List

from ..data.models import Bar


def _closes(bars: List[Bar]) -> List[float]:
    return [b.close for b in bars]


def compute_return_pct(bars: List[Bar], lookback: int) -> float:
    """
    Simple percentage return over the last `lookback` bars.

        ret% = (last_close / past_close - 1) * 100

    If not enough data, returns 0.0.
    """
    closes = _closes(bars)
    if len(closes) <= lookback:
        return 0.0

    last = closes[-1]
    past = closes[-(lookback + 1)]

    if past == 0:
        return 0.0

    return (last / past - 1.0) * 100.0


def compute_multi_horizon_returns(
    bars: List[Bar],
    horizons: List[int] | None = None,
) -> Dict[str, float]:
    """
    Convenience helper: compute returns over multiple lookbacks.

    horizons are in "bars" (for 1D timeframe, 20 ~ 1M, 60 ~ 3M, 120 ~ 6M-ish).

    Returns a dict like:
        {
            "ret_20": <float>,
            "ret_60": <float>,
            "ret_120": <float>,
        }
    """
    if horizons is None:
        horizons = [20, 60, 120]

    result: Dict[str, float] = {}
    for h in horizons:
        key = f"ret_{h}"
        result[key] = compute_return_pct(bars, lookback=h)
    return result
