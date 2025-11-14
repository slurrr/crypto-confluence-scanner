from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Bar:
    """Single OHLCV bar."""
    symbol: str
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SymbolMeta:
    """Basic metadata about a tradable symbol."""
    symbol: str
    base: str
    quote: str
    exchange: str
    is_perp: bool = False


@dataclass
class DerivativesMetrics:
    """Per-symbol derivatives data (funding, OI, etc.)."""
    symbol: str
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    funding_z: Optional[float] = None
    oi_change: Optional[float] = None


@dataclass
class MarketHealth:
    """Snapshot of overall market regime."""
    regime: str  # e.g. "bull", "bear", "sideways", "unknown"
    btc_trend_score: Optional[float] = None
    breadth_score: Optional[float] = None
