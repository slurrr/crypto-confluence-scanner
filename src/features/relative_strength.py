from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Dict, List

from ..data.models import Bar

FeatureDict = Dict[str, float]
ReturnsBySymbol = Dict[str, Dict[str, float]]

# Default RS lookbacks (in bars). 20/60/120 ~= 1M/3M/6M on daily data.
DEFAULT_RS_HORIZONS = [20, 60, 120]
_MIN_RS_BARS = max(DEFAULT_RS_HORIZONS) + 1


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
        horizons = DEFAULT_RS_HORIZONS

    result: Dict[str, float] = {}
    for h in horizons:
        key = f"ret_{h}"
        result[key] = compute_return_pct(bars, lookback=h)
    return result


def percentile_rank(value: float, population: Sequence[float]) -> float:
    """
    Simple percentile rank where the best value gets 100 and the worst gets 0.
    Ties share the same percentile as their position in the sorted ordering.
    """
    clean = [v for v in population if v is not None and isfinite(v)]
    if not clean:
        return 0.0

    n = len(clean)
    if n == 1:
        return 100.0

    lo = min(clean)
    hi = max(clean)
    if hi == lo:
        # Completely flat distribution; treat everyone as middle-of-pack.
        return 50.0

    better = sum(1 for v in clean if v > value)
    pct = (n - better - 1) / (n - 1) * 100.0
    # Clamp for safety
    return max(0.0, min(100.0, pct))


def compute_universe_returns(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
    horizons: Sequence[int] | None = None,
) -> ReturnsBySymbol:
    """
    Compute raw returns for every symbol in the universe.

    Returns a mapping: {symbol: {"ret_20": pct, "ret_60": pct, ...}}.
    Only symbols with enough history for the longest horizon are included.
    """
    if horizons is None:
        horizons = DEFAULT_RS_HORIZONS

    min_bars = max(horizons) + 1
    universe: ReturnsBySymbol = {}
    for symbol, bars in bars_by_symbol.items():
        bar_list = list(bars)
        if len(bar_list) < min_bars:
            continue
        universe[symbol] = compute_multi_horizon_returns(
            bar_list,
            horizons=list(horizons),
        )
    return universe


def compute_rs_features(
    bars: Sequence[Bar],
    universe_returns: Mapping[str, Mapping[str, float]] | None = None,
) -> FeatureDict:
    """
    Canonical Relative Strength feature API.

    Input:
        - bars: OHLCV history for a single symbol/timeframe (oldest -> newest)
        - universe_returns: optional precomputed universe-level RS context
          mapping symbol -> {"ret_20": pct, "ret_60": pct, "ret_120": pct}

    Output:
        - dict of raw RS features with stable snake_case keys.

    Keys (stable schema):
        - rs_ret_20_pct
        - rs_ret_60_pct
        - rs_ret_120_pct
        - rs_20_rank_pct (if universe context provided)
        - rs_60_rank_pct (if universe context provided)
        - rs_120_rank_pct (if universe context provided)
    """
    if len(bars) < _MIN_RS_BARS:
        return {}

    bars_list = list(bars)
    if not bars_list:
        return {}

    symbol = bars_list[0].symbol
    horizons = DEFAULT_RS_HORIZONS

    if universe_returns is not None and symbol in universe_returns:
        rets = dict(universe_returns[symbol])
    else:
        rets = compute_multi_horizon_returns(bars_list, horizons=list(horizons))

    ret_20 = float(rets.get("ret_20", 0.0))
    ret_60 = float(rets.get("ret_60", 0.0))
    ret_120 = float(rets.get("ret_120", 0.0))

    features: FeatureDict = {
        "rs_ret_20_pct": ret_20,
        "rs_ret_60_pct": ret_60,
        "rs_ret_120_pct": ret_120,
        "has_rs_data": 1.0,
    }

    if universe_returns is not None and symbol in universe_returns:
        for h in horizons:
            key = f"ret_{h}"
            val = rets.get(key)
            if val is None or not isfinite(val):
                continue

            population = [
                float(r[key])
                for r in universe_returns.values()
                if key in r and r[key] is not None and isfinite(r[key])
            ]
            if not population:
                continue

            rank_key = f"rs_{h}_rank_pct"
            features[rank_key] = percentile_rank(float(val), population)

    return features
