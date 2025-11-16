from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AlertEvent:
    """
    Represents a single alert that should be sent somewhere (console, Telegram, etc).
    """
    symbol: str
    created_at: datetime
    reason: str              # short label, e.g. "HIGH_CONFLUENCE"
    message: str             # human-readable summary
    confluence_score: float
    trend_score: Optional[float] = None
    vol_score: Optional[float] = None
    volume_score: Optional[float] = None
    rs_score: Optional[float] = None
    positioning_score: Optional[float] = None
    regime_label: Optional[str] = None
