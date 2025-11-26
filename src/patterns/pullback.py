from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from ..data.models import PatternSignal
from .base import PatternContext, get_feature, get_score
from .utils import clamp, pct_change, recent_closes


def _resolve_params(cfg: Mapping[str, Any] | None) -> Dict[str, Any]:
    defaults = {
        "lookback": 15,
        "min_trend_score": 60.0,
        "min_pullback_pct": 2.0,
        "max_pullback_pct": 10.0,
        "ma_proximity_pct": 5.0,
        "max_rvol": 2.0,
        "min_rs_score": 40.0,
        "max_rsi_in_trend": 55.0,  # softer than classic oversold to fit strong trends
    }
    if cfg is None:
        return defaults

    scoped: Mapping[str, Any] = cfg
    if "pullback" in cfg and isinstance(cfg.get("pullback"), Mapping):
        scoped = cfg["pullback"]  # type: ignore[index]

    for key in list(defaults.keys()):
        if key in scoped:
            defaults[key] = scoped[key]
    return defaults


def _compute_rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 2:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    rsi = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for i in range(period, len(closes) - 1):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return rsi


def detect_pullback(
    ctx: PatternContext,
    cfg: Mapping[str, Any] | None = None,
) -> Optional[PatternSignal]:
    """
    Detect pullbacks within an existing uptrend (trend-friendly dip buys).

    Heuristics:
    - Trend score above threshold.
    - Price pulled back between min/max % from recent high.
    - Price near a key moving average (using trend_distance_from_ma_pct).
    - Volume not excessive during pullback.
    - Optional mild RSI cooling in the uptrend.
    """
    params = _resolve_params(cfg)
    lookback = int(params["lookback"])
    min_trend = float(params["min_trend_score"])
    min_pullback_pct = float(params["min_pullback_pct"])
    max_pullback_pct = float(params["max_pullback_pct"])
    ma_proximity_pct = float(params["ma_proximity_pct"])
    max_rvol = float(params["max_rvol"])
    min_rs = float(params["min_rs_score"])
    max_rsi = float(params["max_rsi_in_trend"])

    bars = list(ctx.bars)
    if len(bars) < lookback + 1:
        return None

    closes = [b.close for b in bars]
    recent_window = closes[-(lookback + 1) :]
    recent_high = max(recent_window[:-1])
    last_close = recent_window[-1]
    if recent_high == 0:
        return None

    pullback_pct = pct_change(last_close, recent_high) * -1  # positive when below high
    if pullback_pct < min_pullback_pct or pullback_pct > max_pullback_pct:
        return None

    trend_score = get_score(ctx.scores, "trend_score")
    rs_score = get_score(ctx.scores, "rs_score")
    if trend_score < min_trend or rs_score < min_rs:
        return None

    dist_from_ma = abs(get_feature(ctx.features, "trend_distance_from_ma_pct", default=0.0))
    if dist_from_ma > ma_proximity_pct:
        return None

    rvol = get_feature(ctx.features, "volume_rvol_20_1", default=1.0)
    if rvol > max_rvol:
        return None

    rsi_val = _compute_rsi(recent_closes(bars, min(len(bars), 30)), period=14)
    if rsi_val is not None and rsi_val > max_rsi:
        return None

    pullback_score = clamp((max_pullback_pct - pullback_pct) / max(max_pullback_pct, 1e-6) * 100.0, 0.0, 100.0)
    proximity_score = clamp((ma_proximity_pct - dist_from_ma) / max(ma_proximity_pct, 1e-6) * 100.0, 0.0, 100.0)
    strength = clamp(0.4 * pullback_score + 0.4 * trend_score + 0.2 * rs_score, 0.0, 100.0)
    confidence = clamp((strength + proximity_score) / 2.0, 0.0, 100.0)

    notes = (
        f"Bullish pullback: off {pullback_pct:.2f}% from recent high, "
        f"{dist_from_ma:.2f}% from MA; RVOL {rvol:.2f}"
    )
    extras = {
        "pullback_pct": pullback_pct,
        "dist_from_ma_pct": dist_from_ma,
        "rsi": rsi_val,
        "trend_score": trend_score,
        "rs_score": rs_score,
    }

    return PatternSignal(
        pattern_name="pullback",
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        direction="bullish",
        triggered=True,
        strength=strength,
        confidence=confidence,
        notes=notes,
        extras=extras,
    )
