from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

DEFAULT_REGIME = "sideways"

# If config is totally missing, we’ll fall back to equal weights on these:
DEFAULT_SCORE_KEYS = [
    "trend_score",
    "volume_score",
    "volatility_score",
    "rs_score",
    "positioning_score",
]


def _resolve_regime_weights(
    *,
    cfg: Optional[Mapping[str, Any]],
    regime: Optional[str],
) -> Dict[str, float]:
    """
    Resolve score weights based on regime and config.
    Priority:
      1) cfg['confluence']['regime_weights'][regime]
      2) cfg['confluence']['regime_weights'][default_regime]
      3) equal weights over DEFAULT_SCORE_KEYS
    """
    if cfg is None:
        return _equal_weights(DEFAULT_SCORE_KEYS)

    conf_cfg = cfg.get("confluence", {})
    default_regime = str(conf_cfg.get("default_regime", DEFAULT_REGIME)).lower()
    regime_weights_cfg = conf_cfg.get("regime_weights", {}) or {}

    regime_key = (regime or default_regime).lower()

    # 1) Try requested regime
    weights = regime_weights_cfg.get(regime_key)

    # 2) Fall back to default_regime in config
    if weights is None:
        weights = regime_weights_cfg.get(default_regime)

    # 3) If still nothing, equal weights
    if not weights:
        return _equal_weights(DEFAULT_SCORE_KEYS)

    # Normalize to float dict
    return {str(k): float(v) for k, v in weights.items()}


def _equal_weights(keys: list[str]) -> Dict[str, float]:
    if not keys:
        return {}
    w = 1.0 / len(keys)
    return {k: w for k in keys}


def compute_confluence_score(
    scores: Dict[str, float],
    *,
    weights: Optional[Dict[str, float]] = None,
    regime: Optional[str] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    default_positioning: float = 50.0,
) -> Dict[str, float]:
    """
    Compute a confluence score from component scores.

    - If `weights` is provided, it wins.
    - Else, derive weights from config + regime.
    - If positioning_score is missing/None, treat it as neutral (default_positioning).
    """

    # Ensure positioning_score is present
    if "positioning_score" not in scores or scores["positioning_score"] is None:
        scores = {**scores, "positioning_score": default_positioning}

    # Decide weights
    if weights is None:
        weights = _resolve_regime_weights(cfg=cfg, regime=regime)

    # Weighted sum
    num = 0.0
    denom = 0.0
    for name, w in weights.items():
        value = scores.get(name, 0.0)
        num += w * value
        denom += w

    c = num / denom if denom else 0.0

    # Clamp into [0, 100]
    c = max(0.0, min(100.0, c))

    return {"confluence_score": c}
