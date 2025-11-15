from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..data.models import Bar
from ..features.volatility import (
    compute_atr_percent,
    compute_bb_width_percent,
    compute_volatility_contraction_ratio,
)


@dataclass
class VolatilityScoreResult:
    score: float
    features: Dict[str, float]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _inverse_scale_score(x: float, scale: float = 5.0) -> float:
    """
    Simple inverse scoring: higher x -> lower score.

    score = 100 / (1 + x/scale)

    - scale sets how quickly the score drops.
    """
    if x < 0:
        x = 0.0
    return _clamp(100.0 / (1.0 + (x / scale)))


def _contraction_ratio_score(ratio: float) -> float:
    """
    Volatility contraction ratio:

        ratio = recent_atr% / earlier_atr%

    Heuristic scoring:

        <= 0.5  -> 100 (strong contraction)
         1.0    -> ~100
         1.5    -> ~50
        >= 2.0  -> 0
    """
    # Good when <= 1, bad when >> 1
    # We'll treat ratios in [0, 2] -> [100, 0] with clipping
    if ratio <= 0:
        return 100.0
    if ratio >= 2.0:
        return 0.0

    # Map 0..2 -> 1..0, then scale to 0..100
    normalized = (2.0 - ratio) / 2.0  # 0..1
    return _clamp(normalized * 100.0)


def compute_volatility_score(bars: List[Bar]) -> VolatilityScoreResult:
    """
    Compute a first-pass Volatility Score.

    Idea:
        - Favor lower ATR% (quieter markets vs price)
        - Favor narrower Bollinger Band width% (compression)
        - Favor contraction ratio <= 1 (recent vol < past vol)

    This is "breakout setup"-biased scoring and can be tuned later.
    """
    if len(bars) < 80:
        # Not enough history for contraction calcs; neutral-ish.
        return VolatilityScoreResult(score=50.0, features={})

    atr_pct = compute_atr_percent(bars, period=14)
    bb_width_pct = compute_bb_width_percent(bars, period=20, std_dev=2.0)
    contraction_ratio = compute_volatility_contraction_ratio(
        bars, window_long=60, window_short=20
    )

    s_atr = _inverse_scale_score(atr_pct, scale=5.0)
    s_bb = _inverse_scale_score(bb_width_pct, scale=10.0)
    s_contr = _contraction_ratio_score(contraction_ratio)

    # Blend weights (tunable)
    w_atr = 0.30
    w_bb = 0.35
    w_contr = 0.35

    score = w_atr * s_atr + w_bb * s_bb + w_contr * s_contr

    features = {
        "atr_pct_raw": atr_pct,
        "atr_score": s_atr,
        "bb_width_pct_raw": bb_width_pct,
        "bb_width_score": s_bb,
        "vol_contraction_ratio_raw": contraction_ratio,
        "vol_contraction_ratio_score": s_contr,
    }

    return VolatilityScoreResult(score=_clamp(score), features=features)
