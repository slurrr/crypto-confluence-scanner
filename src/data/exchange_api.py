from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

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
        # If no derivatives client configured, return empty metrics.
        if self._deriv_exchange is None:
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
        derivatives_exchange_id: Optional[str] = None,
    ) -> None:
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"Unsupported CCXT exchange id: {exchange_id}")

        self.exchange_id = exchange_id
        self.exchange = getattr(ccxt, exchange_id)(
            {"enableRateLimit": enable_rate_limit}
        )
        self._configured_symbols = symbols  # e.g. ["BTC/USDT", "ETH/USDT"]

        self._deriv_exchange = None
        self._deriv_markets: Dict[str, Dict[str, Any]] = {}

        if derivatives_exchange_id:
            if not hasattr(ccxt, derivatives_exchange_id):
                raise ValueError(
                    f"Unsupported CCXT derivatives exchange id: {derivatives_exchange_id}"
                )
            self._deriv_exchange = getattr(ccxt, derivatives_exchange_id)(
                {"enableRateLimit": enable_rate_limit}
            )
            # cache markets so we can map spot symbol -> futures symbol
            self._deriv_markets = self._deriv_exchange.load_markets()

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

    # --- Derivatives / mapping ---

    def _map_to_deriv_symbol(self, spot_symbol: str) -> Optional[str]:
        """
        Map a spot-style symbol (e.g. 'BTC/USDT') to a derivatives
        symbol on the futures exchange (e.g. 'BTC/USDT:USDT' on binanceusdm).

        Returns None if no reasonable match is found.
        """
        if self._deriv_exchange is None:
            return None

        # If the futures exchange actually uses the same symbol, great.
        if spot_symbol in self._deriv_markets:
            return spot_symbol

        try:
            base, quote = spot_symbol.split("/")
        except ValueError:
            return None

        # Look for any market with matching base and quote/settle
        for sym, m in self._deriv_markets.items():
            if m.get("base") != base:
                continue

            q = m.get("quote")
            settle = m.get("settle")

            if q == quote or settle == quote:
                return sym

            # Common binanceusdm pattern: BTC/USDT:USDT
            if q == "USDT" and settle == "USDT" and quote == "USDT":
                return sym

        # Last-chance guess for binance-style:
        candidate = f"{base}/USDT:USDT"
        if candidate in self._deriv_markets:
            return candidate

        return None


    # --- Derivatives / positioning ---

    def get_derivatives_metrics(self, symbol: str) -> DerivativesMetrics:
        """
        Fetch funding, open interest, and approximate OI % change from the
        derivatives exchange.

        - funding_rate: current funding (per interval, decimal)
        - open_interest: current OI (contracts or notional, exchange-specific)
        - oi_change: % change in OI over recent history (last vs first)

        If anything isn't available, we just leave that field as None.
        """
        # If no derivatives client configured, return empty metrics.
        if self._deriv_exchange is None:
            return DerivativesMetrics(symbol=symbol)

        deriv_symbol = self._map_to_deriv_symbol(symbol)
        if deriv_symbol is None:
            # Can't map this spot symbol to a futures contract
            return DerivativesMetrics(symbol=symbol)

        funding_rate: Optional[float] = None
        open_interest: Optional[float] = None
        oi_change_pct: Optional[float] = None

        # --- Funding rate ---
        try:
            fr = None
            if hasattr(self._deriv_exchange, "fetchFundingRate"):
                fr = self._deriv_exchange.fetchFundingRate(deriv_symbol)
            elif hasattr(self._deriv_exchange, "fetch_funding_rate"):
                fr = self._deriv_exchange.fetch_funding_rate(deriv_symbol)

            if fr:
                funding_rate = (
                    fr.get("fundingRate")
                    or fr.get("fundingRateDaily")
                    or fr.get("info", {}).get("fundingRate")
                )
                if funding_rate is not None:
                    funding_rate = float(funding_rate)
        except Exception:
            pass

        # --- Current open interest ---
        try:
            oi = None
            if hasattr(self._deriv_exchange, "fetchOpenInterest"):
                oi = self._deriv_exchange.fetchOpenInterest(deriv_symbol)
            elif hasattr(self._deriv_exchange, "fetch_open_interest"):
                oi = self._deriv_exchange.fetch_open_interest(deriv_symbol)

            if oi:
                open_interest = (
                    oi.get("openInterest")
                    or oi.get("openInterestAmount")
                    or oi.get("info", {}).get("openInterest")
                )
                if open_interest is not None:
                    open_interest = float(open_interest)
        except Exception:
            pass

        # --- Open interest history -> % change ---
        try:
            hist = None
            if hasattr(self._deriv_exchange, "fetchOpenInterestHistory"):
                # Try daily history; 7–30 days is plenty for crowding signal
                hist = self._deriv_exchange.fetchOpenInterestHistory(
                    deriv_symbol,
                    timeframe="1d",
                    limit=14,
                )
            elif hasattr(self._deriv_exchange, "fetch_open_interest_history"):
                hist = self._deriv_exchange.fetch_open_interest_history(
                    deriv_symbol,
                    timeframe="1d",
                    limit=14,
                )

            if hist and len(hist) >= 2:
                first = hist[0]
                last = hist[-1]

                def _extract_oi(entry: dict) -> Optional[float]:
                    val = (
                        entry.get("openInterest")
                        or entry.get("openInterestAmount")
                        or entry.get("info", {}).get("openInterest")
                    )
                    return float(val) if val is not None else None

                oi_start = _extract_oi(first)
                oi_end = _extract_oi(last)

                if oi_start and oi_start > 0 and oi_end is not None:
                    oi_change_pct = (oi_end / oi_start - 1.0) * 100.0
        except Exception:
            pass

        return DerivativesMetrics(
            symbol=symbol,
            funding_rate=funding_rate,
            open_interest=open_interest,
            funding_z=None,
            oi_change=oi_change_pct,
        )
