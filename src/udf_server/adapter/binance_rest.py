"""Binance REST API adapter — fetches klines, converts to UDF format."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.udf_server.adapter.resolution import udf_to_binance_interval
from src.udf_server.config import (
    BINANCE_MAX_KLINES_PER_REQUEST,
    BINANCE_MAX_RETRIES,
    BINANCE_RATE_LIMIT_RPM,
    BINANCE_REQUEST_TIMEOUT,
    BINANCE_REST_URL,
    DEFAULT_HISTORY_LIMIT,
)
from src.udf_server.models.bar import Bar

logger = logging.getLogger(__name__)


class BinanceRestAdapter:
    """Fetches historical klines from Binance public REST API.

    No API key required — uses public endpoints exclusively.

    Thread safety: httpx.AsyncClient is NOT thread-safe.
    Use one adapter instance per event-loop.
    """

    def __init__(
        self,
        base_url: str = BINANCE_REST_URL,
        timeout: float = BINANCE_REQUEST_TIMEOUT,
        max_retries: int = BINANCE_MAX_RETRIES,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = asyncio.Semaphore(BINANCE_RATE_LIMIT_RPM)

    async def __aenter__(self) -> BinanceRestAdapter:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Adapter not entered. Use 'async with BinanceRestAdapter()'.")
        return self._client

    async def fetch_klines(
        self,
        symbol: str,
        resolution: str,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Bar]:
        """Fetch OHLCV bars from Binance.

        Args:
            symbol: e.g. "BTCUSDT"
            resolution: UDF resolution string e.g. "60" for 1h
            limit: max bars to return (Binance max: 1000)
            start_time: unix timestamp in SECONDS (optional)
            end_time: unix timestamp in SECONDS (optional)

        Returns:
            List of Bar objects sorted by time ascending.

        Raises:
            ValueError: resolution not supported
            httpx.HTTPError: network or API errors after retries
        """
        interval = udf_to_binance_interval(resolution)

        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, BINANCE_MAX_KLINES_PER_REQUEST),
        }
        if start_time is not None:
            params["startTime"] = start_time * 1000  # Binance uses ms
        if end_time is not None:
            params["endTime"] = end_time * 1000

        data = await self._request_with_retry("/api/v3/klines", params)
        return self._parse_klines(data)

    async def fetch_exchange_info(self) -> dict[str, Any]:
        """Fetch exchange info — used to build symbol cache."""
        return await self._request_with_retry("/api/v3/exchangeInfo", {})

    async def _request_with_retry(
        self,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        """GET with exponential backoff on transient errors."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                async with self._rate_limiter:
                    response = await self.client.get(path, params=params)
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 502, 503, 504) and attempt < self._max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "Binance %d on %s, retry %d/%d after %ds",
                        e.response.status_code,
                        path,
                        attempt + 1,
                        self._max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    last_error = e
                    continue
                raise
            except httpx.RequestError as e:
                if attempt < self._max_retries - 1:
                    wait = 2**attempt
                    logger.warning(
                        "Binance request error on %s: %s, retry %d/%d after %ds",
                        path,
                        e,
                        attempt + 1,
                        self._max_retries,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    last_error = e
                    continue
                raise

        raise last_error  # type: ignore[misc]

    @staticmethod
    def _parse_klines(raw: list[list[str | float]]) -> list[Bar]:
        """Convert Binance kline arrays to Bar objects.

        Binance format: [[open_time, open, high, low, close, volume,
                          close_time, quote_volume, trades, taker_buy_volume,
                          taker_buy_quote_volume, ignore], ...]
        Timestamps: ms → seconds.
        """
        bars: list[Bar] = []
        for k in raw:
            bars.append(
                Bar(
                    time=int(float(k[0])) // 1000,  # ms → seconds
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                )
            )
        return bars
