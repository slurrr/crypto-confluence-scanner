from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .exchange_api import ExchangeAPI
from .models import Bar, SymbolMeta, DerivativesMetrics, MarketHealth

import logging

log = logging.getLogger(__name__)


@dataclass
class DataRepositoryConfig:
    """Lightweight config for the repository."""
    timeframes: Sequence[str]


class DataRepository:
    """
    High-level data access layer used by the rest of the system.

    It wraps an ExchangeAPI implementation and will later also handle
    persistence (PostgreSQL, CSV/Parquet, caching, etc.).
    """

    def __init__(self, api: ExchangeAPI, cfg: DataRepositoryConfig) -> None:
        self.api = api
        self.cfg = cfg

    # --- Universe discovery ---

    def discover_universe(self) -> List[SymbolMeta]:
        symbols = self.api.list_symbols()
        log.info("Discovered %d symbols in universe", len(symbols))
        return symbols

    # --- OHLCV ---

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        return self.api.get_ohlcv(symbol, timeframe, limit=limit)

    # --- Derivatives / positioning ---

    def fetch_derivatives(self, symbol: str) -> DerivativesMetrics:
        return self.api.get_derivatives_metrics(symbol)

    # --- Market health / regime ---

    def compute_market_health(self, universe: Sequence[SymbolMeta]) -> MarketHealth:
        """
        Placeholder stub.

        Later this should call into src.data.market_health and compute
        BTC trend, breadth, and an overall regime label.
        """
        # TODO: implement real regime logic
        return MarketHealth(regime="unknown")
