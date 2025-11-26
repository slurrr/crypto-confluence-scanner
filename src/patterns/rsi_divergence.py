from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from zoneinfo import ZoneInfo

from ..data.models import Bar, PatternSignal
from .base import PatternContext
from .utils import clamp

log = logging.getLogger(__name__)

PATTERN_NAME = "rsi_divergence"

def _compute_rsi(closes: Sequence[float], period: int) -> List[float]:
    """Compute Wilder-style RSI values for the provided closing prices."""
    if len(closes) < period + 2:
        return [float("nan")] * len(closes)

    gains: List[float] = [0.0]
    losses: List[float] = [0.0]
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    rsi: List[float] = [float("nan")] * len(closes)
    rsi[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    for i in range(period + 1, len(closes)):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rsi[i] = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))

    return rsi


def _find_pivots(values: Sequence[float], lookback: int, mode: str) -> List[int]:
    pivots: List[int] = []
    n = len(values)
    for i in range(lookback, n - lookback):
        window = values[i - lookback : i + lookback + 1]
        center = values[i]
        if mode == "high" and center == max(window):
            pivots.append(i)
        if mode == "low" and center == min(window):
            pivots.append(i)
    return pivots


def _last_two(indices: Sequence[int]) -> Optional[tuple[int, int]]:
    if len(indices) < 2:
        return None
    return indices[-2], indices[-1]


def _fmt_time(bar: Bar, tz: str) -> str:
    ts: Optional[datetime] = (
        getattr(bar, "open_time", None)
        or getattr(bar, "timestamp", None)
        or getattr(bar, "time", None)
    )
    if ts is None:
        return "n/a"
    try:
        utc_zone = ZoneInfo("UTC")
    except Exception:
        utc_zone = None

    if ts.tzinfo is None and utc_zone is not None:
        ts = ts.replace(tzinfo=utc_zone)
    try:
        ts = ts.astimezone(ZoneInfo(tz))
    except Exception:
        pass
    return ts.strftime("%Y-%m-%d %H:%M")


def _resolve_params(cfg: Mapping[str, Any] | None) -> Dict[str, Any]:
    params = {
        "period": 14,
        "lookback": 300,
        "pivot_lookback": 3,
        "min_strength": 1.0,
        "max_bars_from_last": 5,
        "debug": False,
        "timezone": "UTC",
    }
    if cfg is None:
        return params

    scoped = cfg
    if (
        isinstance(cfg, Mapping)
        and PATTERN_NAME in cfg
        and isinstance(cfg[PATTERN_NAME], Mapping)
    ):
        scoped = cfg[PATTERN_NAME]

    for key, default in params.items():
        if isinstance(scoped, Mapping) and key in scoped:
            params[key] = scoped[key]
    return params


def _build_signal(
    ctx: PatternContext,
    direction: str,
    price_idx_1: int,
    price_idx_2: int,
    rsi_idx_1: int,
    rsi_idx_2: int,
    prices: Sequence[float],
    rsi: Sequence[float],
    params: Mapping[str, Any],
) -> PatternSignal:
    bars_since = (len(prices) - 1) - price_idx_2
    rsi_delta = rsi[rsi_idx_2] - rsi[rsi_idx_1]
    strength_score = clamp(abs(rsi_delta) * 5.0, 0.0, 100.0)
    recency_score = clamp(100.0 - bars_since * 10.0, 0.0, 100.0)
    confidence = clamp(0.6 * strength_score + 0.4 * recency_score, 0.0, 100.0)

    notes = (
        f"{direction.title()} divergence: price {prices[price_idx_1]:.4f}->{prices[price_idx_2]:.4f}, "
        f"RSI {rsi[rsi_idx_1]:.1f}->{rsi[rsi_idx_2]:.1f}"
    )

    extras = {
        "price_pivots": (price_idx_1, price_idx_2),
        "rsi_pivots": (rsi_idx_1, rsi_idx_2),
        "rsi_delta": rsi_delta,
        "bars_since": bars_since,
        "pivot_times": (
            _fmt_time(ctx.bars[len(ctx.bars) - len(prices) + price_idx_1], params["timezone"]),
            _fmt_time(ctx.bars[len(ctx.bars) - len(prices) + price_idx_2], params["timezone"]),
        ),
    }

    return PatternSignal(
        pattern_name=PATTERN_NAME,
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        direction=direction,
        triggered=True,
        strength=strength_score,
        confidence=confidence,
        notes=notes,
        extras=extras,
    )


def detect_rsi_divergence(
    ctx: PatternContext,
    cfg: Mapping[str, Any] | None = None,
) -> Optional[PatternSignal]:
    """
    Detect classic RSI divergences on the most recent pivots.

    - Bullish: price forms a lower low while RSI forms a higher low.
    - Bearish: price forms a higher high while RSI forms a lower high.
    A signal is emitted only when the latest price pivot is within
    `max_bars_from_last` bars of the most recent bar in the window.
    """
    params = _resolve_params(cfg)
    lookback = int(params["lookback"])
    period = int(params["period"])
    pivot_lb = int(params["pivot_lookback"])
    min_strength = float(params["min_strength"])
    max_bars_from_last = int(params["max_bars_from_last"])
    debug = bool(params.get("debug", False))

    bars = list(ctx.bars)
    if len(bars) < max(lookback, period + 2):
        return None

    recent = bars[-lookback:]
    closes = [b.close for b in recent]
    highs = [b.high for b in recent]
    lows = [b.low for b in recent]

    rsi = _compute_rsi(closes, period)
    if not any(val == val for val in rsi):
        return None

    latest_idx = len(recent) - 1

    price_lows = _find_pivots(lows, pivot_lb, "low")
    rsi_lows = _find_pivots(rsi, pivot_lb, "low")
    bull_signal: Optional[PatternSignal] = None
    lt = _last_two(price_lows)
    lr = _last_two(rsi_lows)
    if lt and lr:
        p1, p2 = lt
        r1, r2 = lr
        if (
            latest_idx - p2 <= max_bars_from_last
            and lows[p2] < lows[p1]
            and rsi[r2] > rsi[r1] + min_strength
        ):
            bull_signal = _build_signal(ctx, "bullish", p1, p2, r1, r2, lows, rsi, params)

    price_highs = _find_pivots(highs, pivot_lb, "high")
    rsi_highs = _find_pivots(rsi, pivot_lb, "high")
    bear_signal: Optional[PatternSignal] = None
    ht = _last_two(price_highs)
    hr = _last_two(rsi_highs)
    if ht and hr:
        h1, h2 = ht
        r1, r2 = hr
        if (
            latest_idx - h2 <= max_bars_from_last
            and highs[h2] > highs[h1]
            and rsi[r2] < rsi[r1] - min_strength
        ):
            bear_signal = _build_signal(ctx, "bearish", h1, h2, r1, r2, highs, rsi, params)

    chosen = None
    if bull_signal and bear_signal:
        chosen = (
            bull_signal
            if (bull_signal.strength or 0) >= (bear_signal.strength or 0)
            else bear_signal
        )
    else:
        chosen = bull_signal or bear_signal

    if chosen and debug:
        log.info(
            "[%s] %s divergence detected (strength=%.2f, confidence=%.2f)",
            ctx.timeframe,
            chosen.direction or "",
            chosen.strength or 0.0,
            chosen.confidence or 0.0,
        )

    return chosen


def detect_rsi_divergence_from_bars(
    bars: Sequence[Bar],
    *,
    timeframe: str = "",
    cfg: Mapping[str, Any] | None = None,
    **legacy_params: Any,
) -> Optional[PatternSignal]:
    """
    Legacy-friendly wrapper to call the pattern using bare bar sequences.

    Additional keyword args (period, lookback, etc.) are merged into the
    pattern config for convenience.
    """
    merged_cfg: Dict[str, Any] = {}
    if cfg:
        merged_cfg.update(cfg if isinstance(cfg, Mapping) else {})
    merged_cfg.update(legacy_params)

    ctx = PatternContext(
        symbol=bars[-1].symbol if bars else "UNKNOWN",
        timeframe=timeframe,
        bars=bars,
        features={},
        scores={},
        confluence_score=None,
        regime=None,
    )
    return detect_rsi_divergence(ctx, merged_cfg)


__all__ = ["detect_rsi_divergence", "detect_rsi_divergence_from_bars", "PATTERN_NAME"]

