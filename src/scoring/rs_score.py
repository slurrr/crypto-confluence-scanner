from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..data.models import Bar
from ..features.relative_strength import compute_multi_horizon_returns


@dataclass
class RelativeStrengthScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _return_score(
    ret_pct: float,
    neg_cap: float = -50.0,
    pos_cap: float = 150.0,
) -> float:
    """
    Map a raw % return to a 0..100 score.

    - returns <= neg_cap  -> 0
    - returns >= pos_cap  -> 100
    - linearly scaled in between

    This is a simple, tunable proxy; we just want a stable scale
    for now.
    """
    if ret_pct <= neg_cap:
        return 0.0
    if ret_pct >= pos_cap:
        return 100.0

    span = pos_cap - neg_cap
    normalized = (ret_pct - neg_cap) / span  # 0..1
    return _clamp(normalized * 100.0)


def compute_relative_strength_score(bars: List[Bar]) -> RelativeStrengthScoreResult:
    """
    First-pass Relative Strength score based on multi-horizon returns.

    Assumes 1 bar ~ 1 day if you're using 1D timeframe:
        - 20 bars  ~ 1 month
        - 60 bars  ~ ~3 months
        - 120 bars ~ ~6 months

    We blend:
        - 1M return
        - 3M return
        - 6M return

    Longer horizons get slightly more weight, but you can tune later.
    """
    # Need enough history to at least compute 3M (60 bars). We'll still
    # compute a degraded score if we have less than 120 bars.
    if len(bars) < 40:
        # Too little data; neutral-ish, empty features.
        return RelativeStrengthScoreResult(score=50.0, features={})

    rets = compute_multi_horizon_returns(bars, horizons=[20, 60, 120])

    ret_20 = rets.get("ret_20", 0.0)
    ret_60 = rets.get("ret_60", 0.0)
    ret_120 = rets.get("ret_120", 0.0)

    s_20 = _return_score(ret_20)
    s_60 = _return_score(ret_60)
    s_120 = _return_score(ret_120)

    # You can tune these weights later; for now:
    # slightly more emphasis on 3M/6M.
    w_20 = 0.25
    w_60 = 0.35
    w_120 = 0.40

    # If we don't have enough bars for 120-bar lookback, its return will
    # be 0 and score mid-ish. You can later make this smarter by tracking
    # which horizons are "valid".
    score = w_20 * s_20 + w_60 * s_60 + w_120 * s_120

    features: Dict[str, float] = {
        "ret_20_raw": ret_20,
        "ret_20_score": s_20,
        "ret_60_raw": ret_60,
        "ret_60_score": s_60,
        "ret_120_raw": ret_120,
        "ret_120_score": s_120,
    }

    return RelativeStrengthScoreResult(score=_clamp(score), features=features)
