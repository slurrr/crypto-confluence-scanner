from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from ..data.models import Bar, PatternSignal


@dataclass
class PatternContext:
    """
    Standard input passed to every pattern detector.

    Attributes
    ----------
    symbol:
        Symbol identifier (e.g. "BTC/USDT").
    timeframe:
        Timeframe string (e.g. "1d").
    bars:
        Historical OHLCV bars ordered oldest->newest.
    features:
        Flat feature dict assembled by the pipeline.
    scores:
        Component scores dict (trend_score, volume_score, etc.).
    confluence_score:
        Final confluence score, if already computed upstream.
    regime:
        Optional market regime label.
    """
    symbol: str
    timeframe: str
    bars: Sequence[Bar]
    features: Mapping[str, Any]
    scores: Mapping[str, float]
    confluence_score: Optional[float] = None
    regime: Optional[str] = None


PatternDetector = Callable[
    [PatternContext, Optional[Mapping[str, Any]]],
    Optional[PatternSignal],
]


def get_score(scores: Mapping[str, float], key: str, default: float = 0.0) -> float:
    """Fetch a score by key, tolerating missing/bad values."""
    try:
        val = scores.get(key, default)
    except AttributeError:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def get_feature(
    features: Mapping[str, Any],
    key: str,
    default: float = 0.0,
) -> float:
    """Fetch a feature by key, tolerating missing/bad values."""
    try:
        val = features.get(key, default)
    except AttributeError:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


__all__ = [
    "PatternContext",
    "PatternDetector",
    "get_feature",
    "get_score",
]
