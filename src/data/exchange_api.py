from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .models import Bar, SymbolMeta, DerivativesMetrics


class ExchangeAPI(ABC):
    """
    Abstract interface for exchange data access.

    Later you can implement CCXT-based or direct REST implementations
    for Binance / Coinbase / Apex Omni, etc.
    """

    @abstractmethod
    def list_symbols(self) -> List[SymbolMeta]:
        """Return all symbols in the trading universe."""
        raise NotImplementedError

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        """Return recent OHLCV bars for a symbol."""
        raise NotImplementedError

    @abstractmethod
    def get_derivatives_metrics(self, symbol: str) -> DerivativesMetrics:
        """Return derivatives / positioning data for a symbol."""
        raise NotImplementedError


class DummyExchangeAPI(ExchangeAPI):
    """
    Minimal placeholder implementation for early development.

    For now, list_symbols returns a tiny hard-coded universe.
    get_ohlcv is left unimplemented on purpose so you remember
    to wire in real data later.
    """

    def list_symbols(self) -> List[SymbolMeta]:
        return [
            SymbolMeta(
                symbol="BTCUSDT",
                base="BTC",
                quote="USDT",
                exchange="binance",
                is_perp=True,
            ),
            SymbolMeta(
                symbol="ETHUSDT",
                base="ETH",
                quote="USDT",
                exchange="binance",
                is_perp=True,
            ),
        ]

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        # TODO: replace with real REST/CCXT calls
        raise NotImplementedError("DummyExchangeAPI.get_ohlcv is not implemented yet")

    def get_derivatives_metrics(self, symbol: str) -> DerivativesMetrics:
        # For now, return empty metrics; safe default.
        return DerivativesMetrics(symbol=symbol)
