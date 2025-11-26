from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Dict, List


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
    regime: str
    btc_trend: Optional[float] = None
    breadth: Optional[float] = None
    risk_on: Optional[float] = None  # NEW
    # optional extras if you want:
    # vol_comfort: Optional[float] = None
    # avg_positioning: Optional[float] = None


@dataclass
class PatternSignal:
    """
    Normalized result emitted by a pattern detector.

    Fields stay intentionally generic so individual pattern modules can stash
    supporting context inside `extras` without widening the shared type.
    """
    pattern_name: str
    symbol: str
    timeframe: str
    triggered: bool = True
    direction: Optional[str] = None  # e.g. "bullish" / "bearish"
    strength: Optional[float] = None  # 0-100 scale
    confidence: Optional[float] = None  # 0-100 scale
    notes: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        """Compact label useful for reports and filters."""
        base = self.pattern_name
        if self.direction:
            base = f"{base}:{self.direction}"
        return base


@dataclass
class ScoreBundle:
    """
    Container for all derived data for a symbol+timeframe snapshot.

    - features: raw feature dict merged from all feature modules
    - scores:   individual score components (trend, volume, etc.)
    - confluence_score: final combined score
    - pattern_signals: pattern-level detections for this symbol
    """
    symbol: str
    timeframe: str

    features: Dict[str, Any] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    confluence_score: float = 0.0
    confidence: Optional[float] = None
    regime: Optional[str] = None
    weights: Dict[str, float] = field(default_factory=dict)
    pattern_signals: List[PatternSignal] = field(default_factory=list)

    @property
    def patterns(self) -> List[str]:
        """
        Backwards-compatible view of pattern labels for ranking/reporting.
        """
        return [sig.label() for sig in self.pattern_signals]
