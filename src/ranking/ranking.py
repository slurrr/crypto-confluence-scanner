from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from ..data.models import Bar, SymbolMeta, DerivativesMetrics
from ..data.repository import DataRepository
from ..scoring.trend_score import compute_trend_score, TrendScoreResult
from ..scoring.volatility_score import (
    compute_volatility_score,
    VolatilityScoreResult,
)
from ..scoring.volume_score import compute_volume_score, VolumeScoreResult
from ..scoring.rs_score import (
    compute_relative_strength_score,
    RelativeStrengthScoreResult,
)
from ..scoring.positioning_score import (
    compute_positioning_score,
    PositioningScoreResult,
)
from ..scoring.confluence import (
    compute_confluence_score,
    ConfluenceScoreResult,
)
from .filters import apply_filters


@dataclass
class RankedSymbol:
    symbol: str
    timeframe: str
    confluence: ConfluenceScoreResult
    trend: TrendScoreResult
    volatility: VolatilityScoreResult
    volume: VolumeScoreResult
    rs: RelativeStrengthScoreResult
    positioning: PositioningScoreResult
    bars: Sequence[Bar]
    meta: SymbolMeta


def score_symbol(
    repo: DataRepository,
    symbol_meta: SymbolMeta,
    timeframe: str,
    bar_limit: int = 200,
) -> RankedSymbol | None:
    """
    Fetch bars & derivatives for a symbol and compute all component scores + confluence.

    Returns None if there's an error or no bars.
    """
    try:
        bars = repo.fetch_ohlcv(symbol_meta.symbol, timeframe, limit=bar_limit)
    except Exception as exc:
        print(f"[WARN] Failed to fetch bars for {symbol_meta.symbol}: {exc}")
        return None

    if not bars:
        print(f"[WARN] No bars for {symbol_meta.symbol}")
        return None

    # Trend / Vol / Volume / RS from OHLCV
    trend = compute_trend_score(bars)
    vol = compute_volatility_score(bars)
    volu = compute_volume_score(bars)
    rs = compute_relative_strength_score(bars)

    # Positioning / funding / OI from derivatives stream
    try:
        deriv = repo.fetch_derivatives(symbol_meta.symbol)
    except Exception as exc:
        print(f"[WARN] Failed to fetch derivatives for {symbol_meta.symbol}: {exc}")
        deriv = DerivativesMetrics(symbol=symbol_meta.symbol)
    positioning = compute_positioning_score(deriv)

    conf = compute_confluence_score(
        symbol=symbol_meta.symbol,
        timeframe=timeframe,
        trend_score=trend.score,
        volatility_score=vol.score,
        volume_score=volu.score,
        rs_score=rs.score,
        positioning_score=positioning.score,
    )

    return RankedSymbol(
        symbol=symbol_meta.symbol,
        timeframe=timeframe,
        confluence=conf,
        trend=trend,
        volatility=vol,
        volume=volu,
        rs=rs,
        positioning=positioning,
        bars=bars,
        meta=symbol_meta,
    )


def rank_universe(
    repo: DataRepository,
    cfg: Dict[str, Any],
    top_n: int = 10,
) -> List[RankedSymbol]:
    """
    Score and rank symbols in the universe by Confluence Score,
    then apply filters and return top_n.
    """
    universe = repo.discover_universe()
    if not universe:
        print("[ERROR] Universe is empty.")
        return []

    timeframe = cfg.get("timeframes", ["1d"])[0]
    ranking_cfg = cfg.get("ranking", {})
    filter_cfg = cfg.get("filters", {})
    max_symbols = ranking_cfg.get("max_symbols", 20)

    symbols_to_scan = universe[:max_symbols]

    ranked: List[RankedSymbol] = []

    for meta in symbols_to_scan:
        r = score_symbol(repo, meta, timeframe=timeframe, bar_limit=200)
        if r is not None:
            ranked.append(r)

    # Apply filters
    filtered = apply_filters(ranked, filter_cfg)

    # Sort descending by confluence score
    filtered.sort(key=lambda r: r.confluence.confluence_score, reverse=True)

    return filtered[:top_n]
