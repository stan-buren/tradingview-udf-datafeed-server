"""In-memory bar cache for real-time WebSocket updates."""

from __future__ import annotations

import time
from collections import deque

from src.udf_server.config import BAR_CACHE_MAX_BARS
from src.udf_server.models.bar import Bar


class BarCache:
    """Thread-unsafe in-memory cache of recent OHLCV bars.

    Keyed by (symbol, resolution). Each value is a deque of Bar
    with maxlen = BAR_CACHE_MAX_BARS.

    Used as a fast path: if history request falls within cached range,
    return from memory instead of hitting Binance REST.
    """

    def __init__(self, max_bars: int = BAR_CACHE_MAX_BARS) -> None:
        self._max_bars = max_bars
        self._cache: dict[tuple[str, str], deque[Bar]] = {}

    def get(
        self,
        symbol: str,
        resolution: str,
        *,
        from_time: int | None = None,
        to_time: int | None = None,
        countback: int | None = None,
    ) -> list[Bar] | None:
        """Get cached bars for a symbol+resolution within time range.

        Returns None if the cache doesn't cover the requested range —
        caller must fall back to REST API.
        """
        key = (symbol.upper(), resolution)
        bars = self._cache.get(key)
        if not bars:
            return None

        # Filter by time range
        result = list(bars)
        if from_time is not None:
            result = [b for b in result if b.time >= from_time]
        if to_time is not None:
            result = [b for b in result if b.time <= to_time]
        if countback is not None and countback > 0:
            result = result[-countback:]

        return result

    def put(self, symbol: str, resolution: str, bars: list[Bar]) -> None:
        """Store bars — replaces existing cache for this key."""
        key = (symbol.upper(), resolution)
        dq = deque(bars[-self._max_bars :], maxlen=self._max_bars)
        self._cache[key] = dq

    def update_bar(self, symbol: str, resolution: str, bar: Bar) -> None:
        """Update or append a single bar (from WebSocket update)."""
        key = (symbol.upper(), resolution)
        if key not in self._cache:
            self._cache[key] = deque(maxlen=self._max_bars)

        bars = self._cache[key]
        if bars and bars[-1].time == bar.time:
            bars[-1] = bar  # Update in-progress bar
        else:
            bars.append(bar)

    def has(self, symbol: str, resolution: str) -> bool:
        """Check if there's any cached data for this key."""
        return (symbol.upper(), resolution) in self._cache

    def clear(self) -> None:
        """Drop all cached bars."""
        self._cache.clear()

    def stats(self) -> dict:
        """Return cache statistics — total symbols * resolutions cached."""
        return {
            "keys": len(self._cache),
            "total_bars": sum(len(v) for v in self._cache.values()),
            "max_bars_per_key": self._max_bars,
        }
