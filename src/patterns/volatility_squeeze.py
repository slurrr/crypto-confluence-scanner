from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ..data.models import PatternSignal
from .base import PatternContext, get_feature, get_score
from .utils import clamp


def _resolve_params(cfg: Mapping[str, Any] | None) -> Dict[str, Any]:
    defaults = {
        "max_bb_width_pct": 6.0,
        "max_contraction_ratio": 1.0,
        "min_volatility_score": 60.0,
        "min_trend_score": 0.0,
        "min_rs_score": 0.0,
    }
    if cfg is None:
        return defaults

    scoped: Mapping[str, Any] = cfg
    if "volatility_squeeze" in cfg and isinstance(cfg.get("volatility_squeeze"), Mapping):
        scoped = cfg["volatility_squeeze"]  # type: ignore[index]

    for key in list(defaults.keys()):
        if key in scoped:
            defaults[key] = scoped[key]
    return defaults


def detect_volatility_squeeze(
    ctx: PatternContext,
    cfg: Mapping[str, Any] | None = None,
) -> Optional[PatternSignal]:
    """
    Detect low-volatility squeezes primed for expansion.

    Conditions:
    - Bollinger Band width below threshold.
    - Volatility contraction ratio at or below threshold.
    - Volatility score high enough to signal compression.
    - Optional trend/RS gates to favor quality names.
    """
    params = _resolve_params(cfg)
    max_bb_width = float(params["max_bb_width_pct"])
    max_contraction = float(params["max_contraction_ratio"])
    min_vol_score = float(params["min_volatility_score"])
    min_trend = float(params["min_trend_score"])
    min_rs = float(params["min_rs_score"])

    bb_width_pct = get_feature(ctx.features, "volatility_bb_width_pct_20")
    contraction = get_feature(ctx.features, "volatility_contraction_ratio_60_20", default=1.0)
    vol_score = get_score(ctx.scores, "volatility_score")
    trend_score = get_score(ctx.scores, "trend_score")
    rs_score = get_score(ctx.scores, "rs_score")
    rvol = get_feature(ctx.features, "volume_rvol_20_1", default=1.0)

    if bb_width_pct <= 0 or bb_width_pct > max_bb_width:
        return None
    if contraction > max_contraction:
        return None
    if vol_score < min_vol_score:
        return None
    if trend_score < min_trend or rs_score < min_rs:
        return None

    compression_score = clamp((max_bb_width - bb_width_pct) / max_bb_width * 100.0, 0.0, 100.0)
    contraction_score = clamp((max_contraction - contraction) / max(max_contraction, 1e-6) * 100.0, 0.0, 100.0)
    strength = clamp(0.4 * compression_score + 0.3 * contraction_score + 0.3 * vol_score, 0.0, 100.0)
    confidence = clamp((strength + trend_score * 0.3 + rs_score * 0.2 + rvol * 10.0) / 2.0, 0.0, 100.0)

    notes = (
        f"Squeeze: BBW {bb_width_pct:.2f}%, ratio {contraction:.2f}, "
        f"vol_score {vol_score:.1f}"
    )
    extras = {
        "bb_width_pct": bb_width_pct,
        "contraction_ratio": contraction,
        "volatility_score": vol_score,
        "trend_score": trend_score,
        "rs_score": rs_score,
        "rvol": rvol,
    }

    return PatternSignal(
        pattern_name="volatility_squeeze",
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        direction=None,
        triggered=True,
        strength=strength,
        confidence=confidence,
        notes=notes,
        extras=extras,
    )
