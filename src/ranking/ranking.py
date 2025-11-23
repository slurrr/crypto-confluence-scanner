from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

from ..data.models import ScoreBundle
from .filters import apply_filters

logger = logging.getLogger(__name__)


@dataclass
class RankingOutput:
    """Container for filtered bundles and derived leaderboards."""
    filtered: List[ScoreBundle]
    leaderboards: Dict[str, List[ScoreBundle]]


def _score_value(bundle: ScoreBundle, key: str) -> float:
    """Safely pull a score value from a ScoreBundle."""
    if key == "confluence_score":
        return float(getattr(bundle, "confluence_score", 0.0) or 0.0)
    try:
        return float((bundle.scores or {}).get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_top_n(
    explicit_top_n: int | None,
    ranking_cfg: Mapping[str, Any],
    reports_cfg: Mapping[str, Any],
    total: int,
) -> int:
    """
    Decide how many symbols to keep in each leaderboard.

    Priority: explicit arg -> ranking.top_n -> reports.top_n -> total.
    """
    for candidate in (
        explicit_top_n,
        ranking_cfg.get("top_n"),
        reports_cfg.get("top_n"),
    ):
        if candidate:
            try:
                n = int(candidate)
                if n > 0:
                    return n
            except (TypeError, ValueError):
                continue
    return total


def _pattern_filter(bundles: Sequence[ScoreBundle], pattern_name: str) -> List[ScoreBundle]:
    """Return bundles whose pattern list contains the given pattern substring (case-insensitive)."""
    pattern_lc = pattern_name.lower()
    matched: List[ScoreBundle] = []
    for b in bundles:
        for p in getattr(b, "patterns", []) or []:
            try:
                if pattern_lc in str(p).lower():
                    matched.append(b)
                    break
            except Exception:
                continue
    return matched


def compile_leaderboards(
    bundles: Sequence[ScoreBundle],
    cfg: Mapping[str, Any] | None,
    *,
    top_n: int | None = None,
) -> Dict[str, List[ScoreBundle]]:
    """
    Build ranking lists from pre-scored, pre-filtered ScoreBundles.

    The caller is responsible for applying filters first.
    """
    cfg = cfg or {}
    ranking_cfg = cfg.get("ranking", {}) or {}
    reports_cfg = cfg.get("reports", {}) or {}
    filters_cfg = cfg.get("filters", {}) or {}

    n = _resolve_top_n(top_n, ranking_cfg, reports_cfg, len(bundles))

    volume_score_min = float(
        ranking_cfg.get(
            "volume_score_min",
            filters_cfg.get("min_volume_score", 0.0),
        )
        or 0.0
    )
    squeeze_min_score_raw = ranking_cfg.get("volatility_score_min")
    squeeze_min_score = float(squeeze_min_score_raw) if squeeze_min_score_raw is not None else 0.0
    watchlist_min = float(ranking_cfg.get("watchlist_confluence_min", 70.0))

    logger.info(
        "[ranking] compiling leaderboards from %d filtered bundles (top_n=%d)",
        len(bundles),
        n,
    )

    sorted_conf = sorted(
        bundles,
        key=lambda b: _score_value(b, "confluence_score"),
        reverse=True,
    )

    top_confluence = sorted_conf[:n]
    top_rs = sorted(
        bundles,
        key=lambda b: _score_value(b, "rs_score"),
        reverse=True,
    )[:n]

    volume_surge = [
        b for b in bundles
        if _score_value(b, "volume_score") >= volume_score_min
    ]
    volume_surge.sort(
        key=lambda b: _score_value(b, "volume_score"),
        reverse=True,
    )
    volume_surge = volume_surge[:n]

    volatility_squeeze = [
        b for b in bundles
        if _score_value(b, "volatility_score") >= squeeze_min_score
    ]
    volatility_squeeze.sort(
        key=lambda b: _score_value(b, "volatility_score"),
        reverse=True,
    )
    volatility_squeeze = volatility_squeeze[:n]

    watchlist_candidates = [
        b for b in bundles
        if _score_value(b, "confluence_score") >= watchlist_min
    ]

    # Pattern-driven lists (future-proofed; empty if patterns not populated yet).
    breakout_list = _pattern_filter(bundles, "breakout")
    pullback_list = _pattern_filter(bundles, "pullback")
    divergence_list = _pattern_filter(bundles, "divergence")

    leaderboards: Dict[str, List[ScoreBundle]] = {
        "all_by_confluence": sorted_conf,
        "top_confluence": top_confluence,
        "top_relative_strength": top_rs,
        "volume_surge": volume_surge,
        "volatility_squeeze": volatility_squeeze,
        "watchlist": watchlist_candidates,
        "breakouts": breakout_list,
        "pullbacks": pullback_list,
        "divergences": divergence_list,
    }

    logger.info(
        "[ranking] leaderboards: confluence=%d rs=%d volume=%d squeeze=%d watchlist=%d",
        len(top_confluence),
        len(top_rs),
        len(volume_surge),
        len(volatility_squeeze),
        len(watchlist_candidates),
    )
    return leaderboards


def rank_score_bundles(
    bundles: Sequence[ScoreBundle],
    cfg: Mapping[str, Any] | None,
    *,
    top_n: int | None = None,
    apply_filtering: bool = True,
) -> RankingOutput:
    """
    Entry point for the pipeline: take scored bundles, optionally filter them,
    then compile leaderboards.
    """
    working = list(bundles)
    if apply_filtering:
        working = apply_filters(working, (cfg or {}).get("filters"))

    leaderboards = compile_leaderboards(working, cfg, top_n=top_n)
    return RankingOutput(filtered=working, leaderboards=leaderboards)
