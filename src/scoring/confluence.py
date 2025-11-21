from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

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


@dataclass
class ConfluenceScoreResult:
    """
    Standard API wrapper for the final confluence score.

    Attributes
    ----------
    confluence_score:
        Final score in [0, 100].

    regime:
        The regime label that was used for weighting
        (e.g. "bull", "sideways", "bear"). This should come
        from MarketHealth or an equivalent regime classifier.

    weights:
        The effective weights used for each canonical component key
        (e.g. {"trend_score": 0.3, ...}).

    component_scores:
        The component scores that were fed into the computation
        (typically ScoreBundle.scores).
    """
    confluence_score: float
    regime: Optional[str]
    weights: Dict[str, float]
    component_scores: Dict[str, float]


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


def _resolve_regime_weights(
    cfg: Optional[Mapping[str, Any]],
    regime: str,
) -> Dict[str, float]:
    """
    Resolve regime-specific weights from config, normalizing keys to canonical
    score names.

    Supports config like:

      confluence:
        regime_weights:
          bull:
            trend: 0.30
            volume: 0.25
            volatility: 0.10
            rs: 0.25
            positioning: 0.10

    or the same with *_score keys.
    """
    if cfg is None:
        # No config at all -> equal weights over the default keys.
        if not DEFAULT_SCORE_KEYS:
            return {}
        equal = 1.0 / len(DEFAULT_SCORE_KEYS)
        return {k: equal for k in DEFAULT_SCORE_KEYS}

    conf_section = _get_confluence_section(cfg)
    regime_weights_root = _get_attr_or_key(conf_section, "regime_weights")

    if regime is None:
        raise ValueError("regime must be provided when cfg-based weights are used")

    regime_key = str(regime).lower()
    regime_map = _get_attr_or_key(regime_weights_root, regime_key, default=None)

    canonical: Dict[str, float] = {}

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

    if not canonical:
        # Nothing configured for this regime -> equal weights fallback.
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
    regime: Optional[str] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> ConfluenceScoreResult:
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

    regime:
        Regime label (e.g. "bull", "sideways", "bear") that has already been
        resolved upstream, usually by MarketHealth / regimes.py.

    cfg:
        Full config object (mapping or OmegaConf). Used to resolve
        confluence.regime_weights if explicit weights are not provided.

    weights:
        Optional explicit weight dict keyed by canonical score keys
        (e.g. "trend_score", "volume_score", ...). If provided, this takes
        precedence over cfg/regime-based resolution.

    Returns
    -------
    ConfluenceScoreResult
        Wrapper containing the final confluence_score plus regime,
        effective weights, and component scores.
    """

    # Copy so we don't mutate the caller's dict
    working_scores: Dict[str, float] = dict(scores)

    # Decide which weights to use
    if weights is None:
        if regime is None:
            raise ValueError("regime is required when weights are not explicitly provided")
        weights = _resolve_regime_weights(cfg, regime)

    effective_weights: Dict[str, float] = dict(weights or {})

    if not effective_weights:
        # No weights at all -> return a structured zero, preserving inputs
        return ConfluenceScoreResult(
            confluence_score=0.0,
            regime=regime,
            weights={},
            component_scores=working_scores,
        )

    num = 0.0
    denom = 0.0

    for name, w in effective_weights.items():
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

    return ConfluenceScoreResult(
        confluence_score=c,
        regime=regime,
        weights=effective_weights,
        component_scores=working_scores,
    )
