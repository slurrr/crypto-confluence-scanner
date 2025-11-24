from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from attr import has

from ..data.models import ScoreBundle
from ..data.repository import DataRepository

from ..features.trend import compute_trend_features
from ..features.volume import compute_volume_features
from ..features.volatility import compute_volatility_features
from ..features.relative_strength import (
    compute_rs_features,
    compute_universe_returns,
)
from ..features.positioning import compute_positioning_features

from ..scoring.trend_score import compute_trend_score
from ..scoring.volume_score import compute_volume_score
from ..scoring.volatility_score import compute_volatility_score
from ..scoring.rs_score import compute_relative_strength_score
from ..scoring.positioning_score import compute_positioning_score
from ..scoring.confluence import compute_confluence_score

from pprint import pprint
from dataclasses import asdict




# ---------- Feature assembly ----------

def compute_all_features(
    bars: List[Any],
    *,
    universe_returns: Optional[Mapping[str, Mapping[str, float]]] = None,
    derivatives: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run all feature modules and merge into a single flat dict.
    Assumes each feature function returns a dict with snake_case keys.
    `universe_returns` should be a symbol->returns mapping computed once per run
    so RS can be ranked cross-sectionally.
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
    
    Prolly get rid of this REQUIRED_KEYS check later and just let each
    scoring function handle missing features gracefully.
    REQUIRED_KEYS = [
        "trend_ma_alignment",
        "trend_persistence",
        "trend_distance_from_ma_pct",
        "trend_ma_slope_pct",
        "volume_rvol_20_1",
        "volume_trend_slope_pct_20_10",
        "volume_percentile_60",
        "volatility_atr_pct_14",
        "volatility_bb_width_pct_20",
        "volatility_contraction_ratio_60_20",
        'rs_ret_20_pct',
        'rs_ret_60_pct',
        'rs_ret_120_pct',
        'rs_20_rank_pct',
        'rs_60_rank_pct',
        'rs_120_rank_pct',
        'has_trend_data',
        'has_volu_data',
        'has_vola_data',
        'has_rs_data',
        'has_deriv_data',
    ]

    # If ANY required features are missing, skip scoring entirely
    for key in REQUIRED_KEYS:
        if key not in features:
            # Skip this symbol
            return {}
    """
    s_trend = compute_trend_score(features)
    s_volume = compute_volume_score(features)
    s_volatility = compute_volatility_score(features)
    s_rs = compute_relative_strength_score(features)
    s_positioning = compute_positioning_score(features)

    # Unwrap any result objects that expose `.score`
    def _as_float(x):
        return x.score if hasattr(x, "score") else x

    scores: Dict[str, float] = {
        "trend_score": _as_float(s_trend),
        "volume_score": _as_float(s_volume),
        "volatility_score": _as_float(s_volatility),
        "rs_score": _as_float(s_rs),
        "positioning_score": _as_float(s_positioning),
    }
    #print("DEBUG raw positioning:", s_positioning)
    #print("DEBUG positioning_score float:", _as_float(s_positioning))

    return scores

# ---------- Confidence assembly ----------

def compute_confluence_confidence(features):
    keys = [k for k in features if k.startswith("has_")]
    flags = [features.get(k, 0) >= 1 for k in keys]
    return sum(flags) / len(flags)


# ---------- ScoreBundle builders ----------

def build_score_bundle_for_bars(
    symbol: str,
    timeframe: str,
    bars: List[Any],
    *,
    universe_returns: Optional[Mapping[str, Mapping[str, float]]] = None,
    derivatives: Optional[Any] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    regime: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None,
) -> ScoreBundle:
    """
    Pure function: from bars (+ optional context) -> ScoreBundle.
    Does NOT touch repositories.
    """
    # 1) compute features
    features = compute_all_features(
        bars,
        universe_returns=universe_returns,
        derivatives=derivatives,
    )

    # 2) compute component scores
    scores = compute_all_scores(features)

    # 3) build base bundle
    bundle = ScoreBundle(
        symbol=symbol,
        timeframe=timeframe,
        features=features,
        scores=scores,
    )

    # 4) compute confluence
    conf = compute_confluence_score(
        scores=bundle.scores,
        regime=regime,
        cfg=cfg,
        weights=weights,
    )

    # 5) compute confidence
    confidence = compute_confluence_confidence(features)


    # 6) attach metadata onto ScoreBundle
    bundle.confluence_score = conf.confluence_score
    bundle.confidence = confidence
    bundle.regime = conf.regime
    bundle.weights = conf.weights

    print("\n--- Debug ScoreBundle ---")
    pprint(asdict(bundle), width=120)

    return bundle


def build_score_bundle_from_repo(
    repo: DataRepository,
    symbol: str,
    timeframe: str,
    *,
    universe_returns: Optional[Mapping[str, Mapping[str, float]]] = None,
    derivatives: Optional[Any] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    regime: Optional[str] = None,
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
        cfg=cfg,
        regime=regime,
        weights=weights,
    )


def compile_score_bundles_for_universe(
    repo: DataRepository,
    symbols: Iterable[str],
    timeframe: str,
    *,
    universe_returns: Optional[Mapping[str, Mapping[str, float]]] = None,
    derivatives_by_symbol: Optional[Dict[str, Any]] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    regime: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[ScoreBundle]:
    """
    High-level helper: loop over a list of symbols and return
    a list of ScoreBundle objects.
    """

    symbol_list = list(symbols)
    bundles: List[ScoreBundle] = []

    # Fetch bars once so we can compute universe-level RS ranks without re-fetching.
    bars_by_symbol: Dict[str, List[Any]] = {}
    for symbol in symbol_list:
        bars_by_symbol[symbol] = repo.fetch_ohlcv(symbol=symbol, timeframe=timeframe)

    universe_ctx = universe_returns
    if universe_ctx is None:
        universe_ctx = compute_universe_returns(bars_by_symbol)

    for symbol in symbol_list:
        derivatives = None
        if derivatives_by_symbol is not None:
            derivatives = derivatives_by_symbol.get(symbol)

        bundle = build_score_bundle_for_bars(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars_by_symbol.get(symbol, []),
            universe_returns=universe_ctx,
            derivatives=derivatives,
            cfg=cfg,
            regime=regime,
            weights=weights,
        )
        # DEBUG: show positioning inputs
        '''
        if symbol == symbols[0]:  # just one symbol to avoid spam
            print(
                "DEBUG positioning for", symbol,
                "funding=",
                bundle.features.get("positioning_funding_rate"),
                "oi_change=",
                bundle.features.get("positioning_oi_change_pct"),
                "has_deriv=",
                bundle.features.get("positioning_has_derivatives_data"),
            )
        '''
        bundles.append(bundle)

    return bundles

