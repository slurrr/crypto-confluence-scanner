from __future__ import annotations

from typing import Any, Mapping, Optional

from ..data.models import PatternSignal
from .base import PatternContext, get_feature, get_score
from .utils import clamp, highest_high, lowest_low, pct_change


def _resolve_params(cfg: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults = {
        "lookback": 20,
        "min_rvol": 1.5,
        "min_trend_score": 50.0,
        "min_volume_score": 50.0,
        "min_rs_score": 0.0,
        "min_confluence": 0.0,
        "allow_bearish": False,
        "break_buffer_pct": 0.1,  # require close beyond pivot by this percent
    }
    if cfg is None:
        return defaults

    scoped: Mapping[str, Any] = cfg
    if "breakout" in cfg and isinstance(cfg.get("breakout"), Mapping):
        scoped = cfg["breakout"]  # type: ignore[index]

    for key in list(defaults.keys()):
        if key in scoped:
            defaults[key] = scoped[key]
    return defaults


def _build_signal(
    ctx: PatternContext,
    direction: str,
    *,
    pivot_price: float,
    breakout_pct: float,
    rvol: float,
    params: Mapping[str, Any],
) -> PatternSignal:
    trend_score = get_score(ctx.scores, "trend_score")
    volume_score = get_score(ctx.scores, "volume_score")
    rs_score = get_score(ctx.scores, "rs_score")
    confluence = ctx.confluence_score or 0.0

    distance_score = clamp(breakout_pct * 10.0, 0.0, 100.0)
    support_score = clamp(
        (0.4 * trend_score) + (0.3 * volume_score) + (0.2 * rs_score) + (0.1 * confluence),
        0.0,
        100.0,
    )
    strength = clamp(0.5 * distance_score + 0.5 * support_score, 0.0, 100.0)
    confidence = clamp(strength * 0.6 + rvol * 10.0, 0.0, 100.0)

    notes = (
        f"{direction.title()} breakout above {pivot_price:.4f} "
        f"by {breakout_pct:.2f}% (RVOL {rvol:.2f})"
    )
    extras = {
        "pivot": pivot_price,
        "breakout_pct": breakout_pct,
        "rvol": rvol,
        "trend_score": trend_score,
        "volume_score": volume_score,
        "rs_score": rs_score,
    }

    return PatternSignal(
        pattern_name="breakout",
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        direction=direction,
        triggered=True,
        strength=strength,
        confidence=confidence,
        notes=notes,
        extras=extras,
    )


def detect_breakout(
    ctx: PatternContext,
    cfg: Mapping[str, Any] | None = None,
) -> Optional[PatternSignal]:
    """
    Detect breakouts above recent resistance (or breakdowns if enabled).

    Conditions (bullish):
    - Last close is above the highest high over `lookback` bars by `break_buffer_pct`.
    - Volume RVOL >= min_rvol.
    - Trend/volume/RS scores exceed configured minimums.
    - Optional confluence score gate if provided.
    """
    params = _resolve_params(cfg)
    lookback = int(params["lookback"])
    allow_bearish = bool(params.get("allow_bearish", False))
    min_rvol = float(params["min_rvol"])
    min_trend = float(params["min_trend_score"])
    min_volume = float(params["min_volume_score"])
    min_rs = float(params["min_rs_score"])
    min_confluence = float(params["min_confluence"])
    break_buffer_pct = float(params["break_buffer_pct"])

    bars = list(ctx.bars)
    if len(bars) < lookback + 1:
        return None

    last_close = bars[-1].close
    pivot_high = highest_high(bars, lookback)
    pivot_low = lowest_low(bars, lookback)

    if pivot_high is None or pivot_low is None:
        return None

    rvol = get_feature(ctx.features, "volume_rvol_20_1", default=1.0)
    trend_score = get_score(ctx.scores, "trend_score")
    volume_score = get_score(ctx.scores, "volume_score")
    rs_score = get_score(ctx.scores, "rs_score")
    confluence_score = ctx.confluence_score or 0.0

    bullish_break = False
    bullish_pct = pct_change(last_close, pivot_high)
    if pivot_high > 0:
        bullish_break = last_close >= pivot_high * (1 + break_buffer_pct / 100.0)

    if bullish_break:
        if (
            rvol >= min_rvol
            and trend_score >= min_trend
            and volume_score >= min_volume
            and rs_score >= min_rs
            and confluence_score >= min_confluence
        ):
            return _build_signal(
                ctx,
                "bullish",
                pivot_price=pivot_high,
                breakout_pct=bullish_pct,
                rvol=rvol,
                params=params,
            )

    if allow_bearish:
        bearish_pct = -pct_change(last_close, pivot_low)  # negative if below
        bearish_break = pivot_low > 0 and last_close <= pivot_low * (1 - break_buffer_pct / 100.0)
        if bearish_break:
            if (
                rvol >= min_rvol
                and trend_score <= 100 - min_trend  # rough inversion for downtrends
                and volume_score >= min_volume
                and confluence_score >= min_confluence
            ):
                return _build_signal(
                    ctx,
                    "bearish",
                    pivot_price=pivot_low,
                    breakout_pct=bearish_pct,
                    rvol=rvol,
                    params=params,
                )

    return None
