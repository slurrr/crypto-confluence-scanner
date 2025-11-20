from __future__ import annotations

from typing import Any, Mapping

from ..data.models import MarketHealth

# Default thresholds used when config does not define them
DEFAULT_REGIME_THRESHOLDS = {
    # Bull requirements
    "bull_min_risk_on": 65.0,
    "bull_min_breadth": 60.0,
    "bull_min_trend": 60.0,

    # Bear requirements
    "bear_max_risk_on": 35.0,
    "bear_max_breadth": 40.0,
    "bear_max_trend": 40.0,
}


def _resolve_thresholds(cfg_section: Mapping[str, Any] | None) -> dict[str, float]:
    """
    Takes cfg['regimes'] (if provided) and merges onto defaults.
    """
    if cfg_section is None:
        return DEFAULT_REGIME_THRESHOLDS.copy()

    merged = DEFAULT_REGIME_THRESHOLDS.copy()
    merged.update({k: float(v) for k, v in cfg_section.items() if isinstance(v, (float, int))})
    return merged


def classify_regime(
    health: MarketHealth,
    cfg: Mapping[str, Any] | None = None,
) -> str:
    """
    Determine market regime from MarketHealth + config thresholds.

    Config structure example:

        regimes:
          bull_min_risk_on: 70
          bull_min_breadth: 55
          bull_min_trend: 60
          bear_max_risk_on: 30
          bear_max_breadth: 35
          bear_max_trend: 40

    If config is not provided, default thresholds are used.
    """
    thresholds = _resolve_thresholds(cfg)

    # Pull metrics
    risk_on = getattr(health, "risk_on", None)
    breadth = getattr(health, "breadth", None)
    trend   = getattr(health, "btc_trend", None)

    # If risk_on is not part of your MarketHealth dataclass yet,
    # you can compute it OR remove the risk_on checks.
    # For now we assume you add risk_on later—safe fallback:
    if risk_on is None:
        # simple fallback proxy
        risk_on = (trend or 50.0 + breadth or 50.0) / 2

    # ---- Bull ----
    if (
        risk_on >= thresholds["bull_min_risk_on"] and
        breadth >= thresholds["bull_min_breadth"] and
        trend   >= thresholds["bull_min_trend"]
    ):
        return "bull"

    # ---- Bear ----
    if (
        risk_on <= thresholds["bear_max_risk_on"] and
        breadth <= thresholds["bear_max_breadth"] and
        trend   <= thresholds["bear_max_trend"]
    ):
        return "bear"

    # ---- Default ----
    return "sideways"
