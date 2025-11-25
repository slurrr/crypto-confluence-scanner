from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, List, TYPE_CHECKING

from .models import MarketHealth, SymbolMeta
from ..scoring.trend_score import compute_trend_score_from_bars
from ..scoring.volatility_score import compute_volatility_score_from_bars
from ..scoring.positioning_score import (
    compute_positioning_score_from_bars_and_derivatives,
)
from ..scoring.regimes import classify_regime  # NEW

if TYPE_CHECKING:
    from .repository import DataRepository


def compute_market_health(
    repo: "DataRepository",
    universe: Sequence[SymbolMeta] | None = None,
) -> MarketHealth:
    """
    Compute a coarse-grained market health snapshot:
    - benchmark trend (BTC)
    - breadth (percentage of symbols in uptrend)
    - benchmark volatility comfort
    - average positioning across universe
    """
    if universe is None:
        universe = repo.discover_universe()

    universe = list(universe)
    if not universe:
        # You can leave risk_on=None here; regimes.classify_regime will fall back
        return MarketHealth(regime="unknown", btc_trend=None, breadth=None, risk_on=None)

    timeframe = (
        repo.cfg.timeframes[0]
        if getattr(repo.cfg, "timeframes", None)
        else "1d"
    )

    symbols = [m.symbol for m in universe]
    benchmark = "BTC/USDT" if "BTC/USDT" in symbols else symbols[0]

    # ---- Benchmark trend + vol ----
    try:
        bench_bars = repo.fetch_ohlcv(benchmark, timeframe, limit=200)
    except Exception:
        bench_bars = []

    if bench_bars:
        t_res = compute_trend_score_from_bars(bench_bars)
        v_res = compute_volatility_score_from_bars(bench_bars)
        btc_trend_score = t_res.score
        btc_vol_score = v_res.score
    else:
        btc_trend_score = 50.0
        btc_vol_score = 50.0

    # ---- Breadth + positioning ----
    uptrend_count = 0
    trend_valid = 0
    positioning_scores: List[float] = []

    for meta in universe:
        symbol = meta.symbol

        try:
            bars = repo.fetch_ohlcv(symbol, timeframe, limit=200)
        except Exception:
            continue

        if not bars:
            continue

        t_res = compute_trend_score_from_bars(bars)
        trend_valid += 1
        if t_res.score >= 60.0:
            uptrend_count += 1

        try:
            deriv = repo.get_derivatives_metrics(symbol)
            p_res = compute_positioning_score_from_bars_and_derivatives(bars, deriv)
            positioning_scores.append(p_res.score)
        except Exception:
            pass

    breadth_pct = (uptrend_count / trend_valid) * 100.0 if trend_valid > 0 else 50.0
    avg_positioning = (
        sum(positioning_scores) / len(positioning_scores)
        if positioning_scores else 50.0
    )

    # ---- Benchmark volatility comfort ----
    vol_offset = abs(btc_vol_score - 50.0)
    vol_comfort = 100.0 - min(100.0, vol_offset * 2.0)
    vol_comfort = max(0.0, min(100.0, vol_comfort))

    # ---- Aggregate risk-on model ----
    w_trend = 0.40
    w_breadth = 0.30
    w_vol = 0.15
    w_pos = 0.15

    risk_on = (
        w_trend * btc_trend_score +
        w_breadth * breadth_pct +
        w_vol * vol_comfort +
        w_pos * avg_positioning
    )
    risk_on = max(0.0, min(100.0, risk_on))

    # Build health snapshot first
    health = MarketHealth(
        regime="unknown",
        btc_trend=btc_trend_score,
        breadth=breadth_pct,
        risk_on=risk_on,
    )

    # Feed through configurable classifier
    regime_cfg = getattr(repo.cfg, "regimes", None)
    health.regime = classify_regime(health, cfg=regime_cfg)

    return health
