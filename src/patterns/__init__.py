from __future__ import annotations

from typing import Any, Dict, Mapping

from .base import PatternContext, PatternDetector
from .breakout import detect_breakout
from .pullback import detect_pullback
from .rsi_divergence import detect_rsi_divergence
from .volatility_squeeze import detect_volatility_squeeze

# Canonical registry of available detectors
PATTERN_REGISTRY: Dict[str, PatternDetector] = {
    "breakout": detect_breakout,
    "pullback": detect_pullback,
    "volatility_squeeze": detect_volatility_squeeze,
    "rsi_divergence": detect_rsi_divergence,
}


def register_pattern(name: str, detector: PatternDetector) -> None:
    """Register a detector under a canonical name."""
    PATTERN_REGISTRY[name] = detector


def get_pattern(name: str) -> PatternDetector | None:
    """Fetch a detector by name if present."""
    return PATTERN_REGISTRY.get(name)


def get_enabled_patterns(
    cfg: Mapping[str, Any] | None = None,
) -> Dict[str, PatternDetector]:
    """
    Return detectors filtered by the `enabled` list in a patterns config block.

    If no enabled list is provided, all registered detectors are returned.
    """
    cfg = cfg or {}
    enabled = cfg.get("enabled")
    if enabled:
        enabled_set = {str(name) for name in enabled}
        return {
            name: det
            for name, det in PATTERN_REGISTRY.items()
            if name in enabled_set
        }
    return dict(PATTERN_REGISTRY)


__all__ = [
    "PatternContext",
    "PatternDetector",
    "PATTERN_REGISTRY",
    "get_enabled_patterns",
    "get_pattern",
    "register_pattern",
]
