from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

import ccxt  # type: ignore

from .models import Bar, SymbolMeta, DerivativesMetrics


class ExchangeAPI(ABC):
    """
    Abstract interface for exchange data access.

    Concrete implementations (like CcxtExchangeAPI) hide the details of
    how OHLCV and derivatives data are fetched.
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
    Minimal placeholder implementation (kept for testing).

    Still here in case you want to run without hitting an API,
    but CcxtExchangeAPI will be the main implementation going forward.
    """

    def list_symbols(self) -> List[SymbolMeta]:
        return [
            SymbolMeta(
                symbol="BTC/USDT",
                base="BTC",
                quote="USDT",
                exchange="dummy",
                is_perp=False,
            ),
            SymbolMeta(
                symbol="ETH/USDT",
                base="ETH",
                quote="USDT",
                exchange="dummy",
                is_perp=False,
            ),
        ]

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        raise NotImplementedError("DummyExchangeAPI.get_ohlcv is not implemented")

    def get_derivatives_metrics(self, symbol: str) -> DerivativesMetrics:
        return DerivativesMetrics(symbol=symbol)


class CcxtExchangeAPI(ExchangeAPI):
    """
    CCXT-based exchange implementation.

    By default this uses the public Binance API (no auth needed) and
    pulls spot OHLCV. Later you can adapt this to perps / futures endpoints
    or Apex-specific APIs.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        symbols: Optional[List[str]] = None,
        enable_rate_limit: bool = True,
    ) -> None:
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"Unsupported CCXT exchange id: {exchange_id}")

        self.exchange = getattr(ccxt, exchange_id)({"enableRateLimit": enable_rate_limit})
        self._configured_symbols = symbols  # e.g. ["BTC/USDT", "ETH/USDT"]

    # --- Universe ---

    def list_symbols(self) -> List[SymbolMeta]:
        if self._configured_symbols:
            ccxt_symbols = self._configured_symbols
        else:
            markets = self.exchange.load_markets()
            # Simple default: all USDT pairs
            ccxt_symbols = [s for s in markets.keys() if s.endswith("/USDT")]

        metas: List[SymbolMeta] = []
        for s in ccxt_symbols:
            try:
                base, quote = s.split("/")
            except ValueError:
                # Fallback if symbol format is unexpected
                base, quote = s, ""
            metas.append(
                SymbolMeta(
                    symbol=s,
                    base=base,
                    quote=quote,
                    exchange=self.exchange.id,
                    is_perp=False,  # you can toggle this for perps later
                )
            )
        return metas

    # --- OHLCV ---

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> List[Bar]:
        """
        Fetch recent OHLCV using CCXT.

        `symbol` is a CCXT symbol like "BTC/USDT".
        """
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        bars: List[Bar] = []
        for ts, o, h, l, c, v in raw:
            bars.append(
                Bar(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(v),
                )
            )
        return bars

    # --- Derivatives / positioning ---

    def get_derivatives_metrics(self, symbol: str) -> DerivativesMetrics:
        """
        Placeholder for funding / OI data.

        For now, returns empty metrics so the rest of the pipeline
        can be implemented without relying on derivatives endpoints.
        """
        return DerivativesMetrics(symbol=symbol)
