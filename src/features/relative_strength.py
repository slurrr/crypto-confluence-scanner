from __future__ import annotations

from collections.abc import Sequence
from typing import Dict, List

from ..data.models import Bar

FeatureDict = Dict[str, float]


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


def compute_rs_features(
    bars: Sequence[Bar],
    universe_returns: Dict[str, float] | None = None,
) -> FeatureDict:
    """
    Canonical Relative Strength feature API.

    Input:
        - bars: OHLCV history for a single symbol/timeframe (oldest -> newest)
        - universe_returns: optional precomputed universe-level RS context
          (not yet used in v1; reserved for future cross-sectional RS).

    Output:
        - dict of raw RS features with stable snake_case keys.

    Keys (stable schema, v1):
        - rs_ret_20_pct
        - rs_ret_60_pct
        - rs_ret_120_pct
    """
    # Keep similar data requirement as original RS score: need some history.
    if len(bars) < 40:
        return None

    bars_list = list(bars)
    rets = compute_multi_horizon_returns(bars_list, horizons=[20, 60, 120])

    ret_20 = rets.get("ret_20", 0.0)
    ret_60 = rets.get("ret_60", 0.0)
    ret_120 = rets.get("ret_120", 0.0)

    features: FeatureDict = {
        "rs_ret_20_pct": ret_20,
        "rs_ret_60_pct": ret_60,
        "rs_ret_120_pct": ret_120,
    }

    # v2: we can add cross-sectional keys here once universe_returns is wired.

    return features
