from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence
from ..data.models import Bar
import zoneinfo
import logging


log = logging.getLogger(__name__)

Kind = Literal["bullish", "bearish", "none"]

def _fmt_bar_time(bar, tz: str = "UTC") -> str:
    """
    Formats a bar's time as 'MM-DD-YYYY HH:MM' in the desired timezone.
    Automatically detects which field the bar uses for time.
    """
    ts = (
        getattr(bar, "timestamp", None)
        or getattr(bar, "time", None)
        or getattr(bar, "open_time", None)
        or getattr(bar, "close_time", None)
    )

    if ts is None:
        return "n/a"

    # If it's a string, try to parse it
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except Exception:
            return ts  # fallback to raw string if unknown format

    # If no timezone on timestamp, assume UTC
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))

    # Apply target timezone
    try:
        target_zone = zoneinfo.ZoneInfo(tz)
        ts = ts.astimezone(target_zone)
    except Exception:
        pass  # if timezone is invalid, keep original

    # Format to: MM-DD-YYYY HH:MM
    return ts.strftime("%m-%d-%Y %H:%M")


@dataclass
class RSIDivergenceResult:
    kind: Kind
    strength: float
    price_idx_1: Optional[int] = None
    price_idx_2: Optional[int] = None
    rsi_idx_1: Optional[int] = None
    rsi_idx_2: Optional[int] = None


def _compute_rsi(closes: Sequence[float], period: int = 14) -> List[float]:
    """
    Simple Wilder-style RSI implementation.
    Returns a list of same length as closes (first values are NaN-like).
    """
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
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        gain = gains[i]
        loss = losses[i]

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def _find_pivots(values: Sequence[float], lookback: int, mode: str) -> List[int]:
    """
    Find local highs / lows using a simple symmetric lookback window.
    Returns indices of pivots.
    mode: "high" or "low"
    """
    pivots: List[int] = []
    n = len(values)
    for i in range(lookback, n - lookback):
        window = values[i - lookback : i + lookback + 1]
        center = values[i]
        if mode == "high":
            if center == max(window):
                pivots.append(i)
        else:
            if center == min(window):
                pivots.append(i)
    return pivots


def _last_two(indices: List[int]) -> Optional[tuple[int, int]]:
    if len(indices) < 2:
        return None
    return indices[-2], indices[-1]


def detect_rsi_divergence(
    bars: Sequence[Bar],
    period: int = 14,
    lookback: int = 150,
    pivot_lookback: int = 3,
    min_strength: float = 5.0,
    max_bars_from_last: int = 1,
    debug: bool = False,
    tz: str = "UTC"
) -> RSIDivergenceResult:
    """
    Detect classic RSI divergence on the last two swing highs/lows:

    - Bullish: price makes a lower low, RSI makes a higher low.
    - Bearish: price makes a higher high, RSI makes a lower high.

    We only consider a divergence valid if the *most recent* price pivot
    (the second pivot) is within `max_bars_from_last` bars of the latest
    bar in the window -> "fresh" signal.

    For debugging, when a divergence is found we log:
      - symbol
      - timestamps of the two price pivots
      - price values at pivots
      - RSI values at corresponding RSI pivots
      - strength
    """
    if len(bars) < max(lookback, period + 10):
        return RSIDivergenceResult(kind="none", strength=0.0)

    # Use the last 'lookback' bars to avoid super old pivots.
    recent = list(bars)[-lookback:]
    closes = [b.close for b in recent]
    highs = [b.high for b in recent]
    lows = [b.low for b in recent]

    rsi = _compute_rsi(closes, period=period)
    if all(val != val for val in rsi):  # NaN check: rsi != rsi when NaN
        return RSIDivergenceResult(kind="none", strength=0.0)

    latest_idx = len(recent) - 1  # index of most recent bar
    symbol = recent[-1].symbol if recent else "UNKNOWN"

    # --- Bullish divergence: price lower low, RSI higher low ---
    price_lows = _find_pivots(lows, pivot_lookback, mode="low")
    rsi_lows = _find_pivots(rsi, pivot_lookback, mode="low")

    bull = RSIDivergenceResult(kind="none", strength=0.0)
    lt = _last_two(price_lows)
    lr = _last_two(rsi_lows)

    if lt and lr:
        p1, p2 = lt
        r1, r2 = lr

        # Require the most recent price pivot to be near the right edge
        if latest_idx - p2 <= max_bars_from_last:
            if lows[p2] < lows[p1] and rsi[r2] > rsi[r1] + min_strength:
                strength = rsi[r2] - rsi[r1]
                bull = RSIDivergenceResult(
                    kind="bullish",
                    strength=strength,
                    price_idx_1=p1,
                    price_idx_2=p2,
                    rsi_idx_1=r1,
                    rsi_idx_2=r2,
                )

                # --- DEBUG LOGGING FOR BULLISH DIVERGENCE ---
                if debug:
                    bar_p1 = recent[p1]
                    bar_p2 = recent[p2]
                    rsi1 = rsi[r1]
                    rsi2 = rsi[r2]
                    t1 = _fmt_bar_time(bar_p1, tz)
                    t2 = _fmt_bar_time(bar_p2, tz)

                    log.info(
                        "\n"
                        "===== RSI DIVERGENCE (BULLISH) =====\n"
                        "Symbol : %s\n"
                        "Price  : %.8f -> %.8f  (lower low)\n"
                        "Time   : %s (idx %d) -> %s (idx %d)\n"
                        "RSI    : %.2f -> %.2f  (Δ=%.2f)\n"
                        "Pivots : price (%d -> %d), rsi (%d -> %d)\n"
                        "====================================",
                        symbol,
                        bar_p1.low,
                        bar_p2.low,
                        t1,
                        p1,
                        t2,
                        p2,
                        rsi1,
                        rsi2,
                        strength,
                        p1,
                        p2,
                        r1,
                        r2,
                    )



    # --- Bearish divergence: price higher high, RSI lower high ---
    price_highs = _find_pivots(highs, pivot_lookback, mode="high")
    rsi_highs = _find_pivots(rsi, pivot_lookback, mode="high")

    bear = RSIDivergenceResult(kind="none", strength=0.0)
    ht = _last_two(price_highs)
    hr = _last_two(rsi_highs)

    if ht and hr:
        h1, h2 = ht
        r1, r2 = hr

        if latest_idx - h2 <= max_bars_from_last:
            if highs[h2] > highs[h1] and rsi[r2] < rsi[r1] - min_strength:
                strength = rsi[r1] - rsi[r2]
                bear = RSIDivergenceResult(
                    kind="bearish",
                    strength=strength,
                    price_idx_1=h1,
                    price_idx_2=h2,
                    rsi_idx_1=r1,
                    rsi_idx_2=r2,
                )

                # --- DEBUG LOGGING FOR BEARISH DIVERGENCE ---
                if debug:
                    bar_p1 = recent[h1]
                    bar_p2 = recent[h2]
                    rsi1 = rsi[r1]
                    rsi2 = rsi[r2]
                    t1 = _fmt_bar_time(bar_p1, tz)
                    t2 = _fmt_bar_time(bar_p2, tz)

                    log.info(
                        "\n"
                        "===== RSI DIVERGENCE (BEARISH) =====\n"
                        "Symbol : %s\n"
                        "Price  : %.8f -> %.8f  (higher high)\n"
                        "Time   : %s (idx %d) -> %s (idx %d)\n"
                        "RSI    : %.2f -> %.2f  (Δ=%.2f)\n"
                        "Pivots : price (%d -> %d), rsi (%d -> %d)\n"
                        "====================================",
                        symbol,
                        bar_p1.high,
                        bar_p2.high,
                        t1,
                        h1,
                        t2,
                        h2,
                        rsi1,
                        rsi2,
                        strength,
                        h1,
                        h2,
                        r1,
                        r2,
                    )




    # Pick the stronger signal if both exist (rare, but possible)
    if bull.kind == "bullish" and bear.kind == "bearish":
        return bull if bull.strength >= bear.strength else bear
    if bull.kind == "bullish":
        return bull
    if bear.kind == "bearish":
        return bear

    return RSIDivergenceResult(kind="none", strength=0.0)

