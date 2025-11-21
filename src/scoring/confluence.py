from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# Fallback regime if nothing is configured / passed
DEFAULT_REGIME = "sideways"

# If config is totally missing, we’ll fall back to equal weights on these:
DEFAULT_SCORE_KEYS = [
    "trend_score",
    "volume_score",
    "volatility_score",
    "rs_score",
    "positioning_score",
]

# Map short config names → canonical score keys used in ScoreBundle.scores
SCORE_KEY_ALIASES: Dict[str, str] = {
    "trend": "trend_score",
    "trend_score": "trend_score",
    "volume": "volume_score",
    "volume_score": "volume_score",
    "volatility": "volatility_score",
    "volatility_score": "volatility_score",
    "rs": "rs_score",
    "rs_score": "rs_score",
    "positioning": "positioning_score",
    "positioning_score": "positioning_score",
}


# ---------------------------------------------------------------------------
# Small helpers to safely read from both dict-like configs and OmegaConf-style
# objects (cfg.confluence.regime_weights, etc.)
# ---------------------------------------------------------------------------

def _get_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Try getattr, then mapping-style .get, otherwise default."""
    if obj is None:
        return default

    # OmegaConf / attr-style
    try:
        value = getattr(obj, key)
        # OmegaConf returns MISSING sometimes; treat falsy as missing
        if value is not None:
            return value
    except AttributeError:
        pass

    # Mapping-style
    if isinstance(obj, Mapping):
        return obj.get(key, default)

    return default


def _get_confluence_section(cfg: Optional[Mapping[str, Any]]) -> Any:
    if cfg is None:
        return None
    return _get_attr_or_key(cfg, "confluence", cfg)


def _resolve_regime(regime: Optional[str], cfg: Optional[Mapping[str, Any]]) -> str:
    conf_section = _get_confluence_section(cfg)
    default_regime = _get_attr_or_key(conf_section, "default_regime", DEFAULT_REGIME)
    return (regime or default_regime or DEFAULT_REGIME).lower()


def _resolve_regime_weights(
    cfg: Optional[Mapping[str, Any]],
    regime: Optional[str],
) -> Dict[str, float]:
    """
    Resolve regime-specific weights from config, normalizing keys to canonical
    score names.

    Supports config like:

      confluence:
        default_regime: sideways
        regime_weights:
          bull:
            trend: 0.30
            volume: 0.25
            volatility: 0.10
            rs: 0.25
            positioning: 0.10
          ...

    or the same with *_score keys.
    """
    # If there is no cfg at all, fall back to equal weights.
    if cfg is None:
        if not DEFAULT_SCORE_KEYS:
            return {}
        equal = 1.0 / len(DEFAULT_SCORE_KEYS)
        return {k: equal for k in DEFAULT_SCORE_KEYS}

    conf_section = _get_confluence_section(cfg)
    regime_weights_root = _get_attr_or_key(conf_section, "regime_weights")

    resolved_regime = _resolve_regime(regime, cfg)

    # Grab the mapping for this regime, if present
    regime_map = _get_attr_or_key(regime_weights_root, resolved_regime, default=None)

    canonical: Dict[str, float] = {}

    # Best case: regime_map is mapping-like, so we can iterate directly
    if isinstance(regime_map, Mapping):
        items = regime_map.items()
    else:
        # Fallback: try to pull known alias keys as attributes
        items = []
        for raw_key in SCORE_KEY_ALIASES.keys():
            val = getattr(regime_map, raw_key, None) if regime_map is not None else None
            if val is not None:
                items.append((raw_key, val))

    for raw_key, weight in items:
        if weight is None:
            continue
        canonical_key = SCORE_KEY_ALIASES.get(str(raw_key))
        if canonical_key is None:
            continue
        try:
            w = float(weight)
        except (TypeError, ValueError):
            continue
        canonical[canonical_key] = w

    # If nothing was configured / resolved, fall back to equal weights
    if not canonical:
        if not DEFAULT_SCORE_KEYS:
            return {}
        equal = 1.0 / len(DEFAULT_SCORE_KEYS)
        return {k: equal for k in DEFAULT_SCORE_KEYS}

    return canonical


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_confluence_score(
    scores: Dict[str, float],
    *,
    weights: Optional[Dict[str, float]] = None,
    regime: Optional[str] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    default_positioning: float = 50.0,
) -> Dict[str, float]:
    """
    Compute a final confluence_score in the range [0, 100].

    Parameters
    ----------
    scores:
        Dict of individual component scores, typically from ScoreBundle.scores,
        e.g. {
            "trend_score": 75.0,
            "volume_score": 40.0,
            "volatility_score": 55.0,
            "rs_score": 65.0,
            "positioning_score": 20.0,
            ...
        }

    weights:
        Optional explicit weight dict keyed by canonical score keys
        (e.g. "trend_score", "volume_score", ...). If provided, this wins.

    regime:
        Optional regime label (e.g. "bull", "sideways", "bear").
        If omitted, we’ll use confluence.default_regime from config or
        DEFAULT_REGIME.

    cfg:
        Full config object (mapping or OmegaConf). Used to resolve
        confluence.regime_weights and confluence.default_regime.

    default_positioning:
        If "positioning_score" is missing from `scores`, this default is used
        so that positioning can still contribute under regime weighting.

    Returns
    -------
    dict:
        {"confluence_score": float in [0, 100]}
    """
    # Start from a shallow copy so we don't mutate caller's dict
    working_scores: Dict[str, float] = dict(scores)

    # Ensure positioning has *some* value if regime weighting expects it
    working_scores.setdefault("positioning_score", default_positioning)

    # Decide which weights to use
    if weights is None:
        weights = _resolve_regime_weights(cfg, regime)

    if not weights:
        # No weights at all → no contribution; just return 0.0
        return {"confluence_score": 0.0}

    # Weighted sum over *available* scores, skipping missing/None values
    num = 0.0
    denom = 0.0

    for name, w in weights.items():
        value = working_scores.get(name)
        if value is None:
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        num += w * v
        denom += w

    c = num / denom if denom else 0.0

    # Clamp into [0, 100]
    if c < 0.0:
        c = 0.0
    elif c > 100.0:
        c = 100.0

    return {"confluence_score": c}
