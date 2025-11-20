from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Any
from .exchange_api import ExchangeAPI
from .models import Bar, SymbolMeta, DerivativesMetrics

from .market_health import compute_market_health  # runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import MarketHealth  # for type hints only


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
        #max_syms = self.cfg.max_symbols
        # Apply limit if configured
        #if max_syms is not None:
        #    symbols = symbols[:max_syms]
        self._universe_cache = list(symbols)
        log.info("Discovered %d symbols in universe", len(self._universe_cache))
        return self._universe_cache

    # --- OHLCV ---

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        return self.api.get_ohlcv(symbol, timeframe, limit=limit)

    # --- Derivatives / positioning ---

    def fetch_derivatives(self, symbol: str) -> DerivativesMetrics:
        return self.api.get_derivatives_metrics(symbol)

   # --- Market Health ---

    def compute_market_health(self, universe=None) -> MarketHealth:
        return compute_market_health(self, universe)