from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence
from .exchange_api import ExchangeAPI
from .models import Bar, SymbolMeta, DerivativesMetrics, MarketHealth

from ..scoring.trend_score import compute_trend_score, compute_trend_score_from_bars
from ..scoring.volatility_score import compute_volatility_score, compute_volatility_score_from_bars
from ..scoring.positioning_score import compute_positioning_score, compute_positioning_score_from_bars_and_derivatives, compute_positioning_score_from_derivatives

import logging

log = logging.getLogger(__name__)


@dataclass
class DataRepositoryConfig:
    """Lightweight config for the repository."""
    timeframes: Sequence[str]
    max_symbols: Optional[int] = None    # limit for universe discovery
    

class DataRepository:
    """
    High-level data access layer used by the rest of the system.

    It wraps an ExchangeAPI implementation and will later also handle
    persistence (PostgreSQL, CSV/Parquet, caching, etc.).
    """

    def __init__(self, api: ExchangeAPI, cfg: DataRepositoryConfig) -> None:
        self.api = api
        self.cfg = cfg
        self._universe_cache: list[SymbolMeta] | None = None

    # --- Universe discovery ---

    def discover_universe(self) -> List[SymbolMeta]:
        """
        Discover the trading universe once and cache it for this run.
        Subsequent calls reuse the cached result and do not log again.
        """
        if self._universe_cache is not None:
            return self._universe_cache

        symbols = self.api.list_symbols()
        # Get max_symbols from config (optional)
        max_syms = self.cfg.max_symbols
        # Apply limit if configured
        if max_syms is not None:
            symbols = symbols[:max_syms]
        self._universe_cache = list(symbols)
        log.info("Discovered %d symbols in universe", len(self._universe_cache))
        return self._universe_cache

    # --- OHLCV ---

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        return self.api.get_ohlcv(symbol, timeframe, limit=limit)

    # --- Derivatives / positioning ---

    def fetch_derivatives(self, symbol: str) -> DerivativesMetrics:
        return self.api.get_derivatives_metrics(symbol)

    # --- Market health / regime ---

    def compute_market_health(
        self,
        universe: Sequence[SymbolMeta] | None = None,
    ) -> MarketHealth:
        """
        Full-quant v1 market health:

        - BTC (benchmark) trend score
        - Market breadth (% of symbols in uptrend)
        - BTC volatility "comfort"
        - Average positioning (funding + OI) across universe
        - Aggregate risk-on score -> bull / bear / sideways regime
        """
        # Get universe if not provided
        if universe is None:
            universe = self.discover_universe()

        universe = list(universe)
        if not universe:
            return MarketHealth(
                regime="unknown",
                btc_trend=None,
                breadth=None,
            )

        # Timeframe: use first configured, fallback to "1d"
        timeframe = (
            self.cfg.timeframes[0] if getattr(self.cfg, "timeframes", None) else "1d"
        )

        symbols = [m.symbol for m in universe]

        # Pick benchmark: BTC/USDT if present, else first symbol
        if "BTC/USDT" in symbols:
            benchmark = "BTC/USDT"
        else:
            benchmark = symbols[0]

        # --- Benchmark trend & volatility ---
        try:
            bench_bars = self.fetch_ohlcv(benchmark, timeframe, limit=200)
        except Exception:
            bench_bars = []

        if bench_bars:
            bench_trend = compute_trend_score_from_bars(bench_bars)
            bench_vol = compute_volatility_score_from_bars(bench_bars)
            btc_trend_score = bench_trend.score
            btc_vol_score = bench_vol.score
        else:
            btc_trend_score = 50.0
            btc_vol_score = 50.0

        # --- Breadth & positioning across universe ---
        uptrend_count = 0
        trend_valid = 0
        positioning_scores: list[float] = []

        for meta in universe:
            symbol = meta.symbol

            # Trend per symbol
            try:
                bars = self.fetch_ohlcv(symbol, timeframe, limit=200)
            except Exception:
                continue

            if not bars:
                continue

            t_res = compute_trend_score_from_bars(bars)
            trend_valid += 1
            if t_res.score >= 60.0:
                uptrend_count += 1

            # Positioning per symbol (funding + OI change)
            try:
                deriv = self.fetch_derivatives(symbol)
                pos_res = compute_positioning_score_from_bars_and_derivatives(bars, deriv)
                positioning_scores.append(pos_res.score)
            except Exception:
                # Not all symbols have derivatives; that's fine.
                pass

        if trend_valid > 0:
            breadth_pct = (uptrend_count / trend_valid) * 100.0
        else:
            breadth_pct = 50.0

        if positioning_scores:
            avg_positioning = sum(positioning_scores) / len(positioning_scores)
        else:
            avg_positioning = 50.0

        # Volatility comfort: mid-range better than extremes
        vol_offset = abs(btc_vol_score - 50.0)
        vol_comfort = 100.0 - min(100.0, vol_offset * 2.0)
        vol_comfort = max(0.0, min(100.0, vol_comfort))

        # Aggregate risk-on score (tunable weights)
        w_trend = 0.40
        w_breadth = 0.30
        w_vol = 0.15
        w_pos = 0.15

        risk_on = (
            w_trend * btc_trend_score
            + w_breadth * breadth_pct
            + w_vol * vol_comfort
            + w_pos * avg_positioning
        )
        risk_on = max(0.0, min(100.0, risk_on))

        # Regime classification
        if risk_on >= 65.0 and breadth_pct >= 60.0 and btc_trend_score >= 60.0:
            regime_label = "bull"
        elif risk_on <= 35.0 and breadth_pct <= 40.0 and btc_trend_score <= 40.0:
            regime_label = "bear"
        else:
            regime_label = "sideways"

        return MarketHealth(
            regime=regime_label,
            btc_trend=btc_trend_score,
            breadth=breadth_pct,
        )
