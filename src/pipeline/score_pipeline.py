from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from data.models import ScoreBundle
from data.repository import DataRepository

from features.trend import compute_trend_features
from features.volume import compute_volume_features
from features.volatility import compute_volatility_features
from features.relative_strength import compute_rs_features
from features.positioning import compute_positioning_features

# Adjust imports to your actual score module names / APIs
from scoring.trend_score import compute_trend_score
from scoring.volume_score import compute_volume_score
from scoring.volatility_score import compute_volatility_score
from scoring.rs_score import compute_relative_strength_score
from scoring.positioning_score import compute_positioning_score
from scoring.confluence import compute_confluence_score



# ---------- Feature assembly ----------

def compute_all_features(
    bars: List[Any],
    *,
    universe_returns: Optional[Any] = None,
    derivatives: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run all feature modules and merge into a single flat dict.
    Assumes each feature function returns a dict with snake_case keys.
    """

    feat_trend = compute_trend_features(bars)
    feat_volume = compute_volume_features(bars)
    feat_volatility = compute_volatility_features(bars)
    feat_rs = compute_rs_features(bars, universe_returns=universe_returns)
    feat_positioning = compute_positioning_features(bars, derivatives=derivatives)

    # Left-biased merge; later modules can override earlier keys if needed.
    features: Dict[str, Any] = {
        **feat_trend,
        **feat_volume,
        **feat_volatility,
        **feat_rs,
        **feat_positioning,
    }
    return features


# ---------- Score assembly ----------

def compute_all_scores(features: Dict[str, Any]) -> Dict[str, float]:
    """
    Run all score modules and merge results into a single dict.

    Each `compute_*_scores` is expected to return a dict, e.g.:
      {"trend_score": 37.5}
    """
    s_trend = compute_trend_score(features)
    s_volume = compute_volume_score(features)
    s_volatility = compute_volatility_score(features)
    s_rs = compute_relative_strength_score(features)
    s_positioning = compute_positioning_score(features)

    scores: Dict[str, float] = {
        **s_trend,
        **s_volume,
        **s_volatility,
        **s_rs,
        **s_positioning,
    }
    return scores


# ---------- ScoreBundle builders ----------

def build_score_bundle_for_bars(
    symbol: str,
    timeframe: str,
    bars: List[Any],
    *,
    universe_returns: Optional[Any] = None,
    derivatives: Optional[Any] = None,
    weights: Optional[Dict[str, float]] = None,
) -> ScoreBundle:
    """
    Pure function: from bars (+ optional context) -> ScoreBundle.
    Does NOT touch repositories.
    """
    features = compute_all_features(
        bars,
        universe_returns=universe_returns,
        derivatives=derivatives,
    )
    scores = compute_all_scores(features)
    confluence = compute_confluence_score(scores, weights=weights)["confluence_score"]

    return ScoreBundle(
        symbol=symbol,
        timeframe=timeframe,
        features=features,
        scores=scores,
        confluence_score=confluence,
        patterns=[],  # hook for pattern detection later
    )


def build_score_bundle_from_repo(
    repo: DataRepository,
    symbol: str,
    timeframe: str,
    *,
    universe_returns: Optional[Any] = None,
    derivatives: Optional[Any] = None,
    weights: Optional[Dict[str, float]] = None,
) -> ScoreBundle:
    """
    Convenience wrapper that uses the data repository to fetch bars,
    then delegates to `build_score_bundle_for_bars`.
    """
    bars = repo.fetch_ohlcv(symbol=symbol, timeframe=timeframe)
    return build_score_bundle_for_bars(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        universe_returns=universe_returns,
        derivatives=derivatives,
        weights=weights,
    )


def compile_score_bundles_for_universe(
    repo: DataRepository,
    symbols: Iterable[str],
    timeframe: str,
    *,
    universe_returns: Optional[Any] = None,
    derivatives_by_symbol: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[ScoreBundle]:
    """
    High-level helper: loop over a list of symbols and return
    a list of ScoreBundle objects.
    """

    bundles: List[ScoreBundle] = []

    for symbol in symbols:
        derivatives = None
        if derivatives_by_symbol is not None:
            derivatives = derivatives_by_symbol.get(symbol)

        bundle = build_score_bundle_from_repo(
            repo=repo,
            symbol=symbol,
            timeframe=timeframe,
            universe_returns=universe_returns,
            derivatives=derivatives,
            weights=weights,
        )
        bundles.append(bundle)

    return bundles
