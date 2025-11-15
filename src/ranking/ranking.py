from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from ..data.models import Bar, SymbolMeta
from ..data.repository import DataRepository
from ..scoring.trend_score import compute_trend_score
from ..scoring.volatility_score import compute_volatility_score
from ..scoring.volume_score import compute_volume_score
from ..scoring.rs_score import compute_relative_strength_score
from ..scoring.confluence import compute_confluence_score, ConfluenceScoreResult


@dataclass
class RankedSymbol:
    symbol: str
    timeframe: str
    confluence: ConfluenceScoreResult
    bars: Sequence[Bar]
    meta: SymbolMeta


def score_symbol(
    repo: DataRepository,
    symbol_meta: SymbolMeta,
    timeframe: str,
    bar_limit: int = 200,
) -> RankedSymbol | None:
    """
    Fetch bars for a symbol and compute all component scores + confluence.

    Returns None if there's an error or no bars.
    """
    try:
        bars = repo.fetch_ohlcv(symbol_meta.symbol, timeframe, limit=bar_limit)
    except Exception as exc:
        # In production you'd want structured logging here.
        print(f"[WARN] Failed to fetch bars for {symbol_meta.symbol}: {exc}")
        return None

    if not bars:
        print(f"[WARN] No bars for {symbol_meta.symbol}")
        return None

    trend = compute_trend_score(bars)
    vol = compute_volatility_score(bars)
    volu = compute_volume_score(bars)
    rs = compute_relative_strength_score(bars)

    conf = compute_confluence_score(
        symbol=symbol_meta.symbol,
        timeframe=timeframe,
        trend_score=trend.score,
        volatility_score=vol.score,
        volume_score=volu.score,
        rs_score=rs.score,
    )

    return RankedSymbol(
        symbol=symbol_meta.symbol,
        timeframe=timeframe,
        confluence=conf,
        bars=bars,
        meta=symbol_meta,
    )


def rank_universe(
    repo: DataRepository,
    cfg: Dict[str, Any],
    top_n: int = 10,
) -> List[RankedSymbol]:
    """
    Score and rank symbols in the universe by Confluence Score.

    Uses:
      - universe from repo.discover_universe()
      - first timeframe from cfg["timeframes"]
      - optional cfg["ranking"]["max_symbols"] to limit the scan
    """
    universe = repo.discover_universe()
    if not universe:
        print("[ERROR] Universe is empty.")
        return []

    timeframe = cfg.get("timeframes", ["1d"])[0]
    ranking_cfg = cfg.get("ranking", {})
    max_symbols = ranking_cfg.get("max_symbols", 20)

    # To avoid hammering the API while experimenting, we can cap the universe
    symbols_to_scan = universe[:max_symbols]

    ranked: List[RankedSymbol] = []

    for meta in symbols_to_scan:
        r = score_symbol(repo, meta, timeframe=timeframe, bar_limit=200)
        if r is not None:
            ranked.append(r)

    # Sort descending by confluence score
    ranked.sort(key=lambda r: r.confluence.confluence_score, reverse=True)

    return ranked[:top_n]
