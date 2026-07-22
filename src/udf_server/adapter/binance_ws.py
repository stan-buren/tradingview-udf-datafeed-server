"""Binance WebSocket adapter — real-time kline streams → bar cache."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from src.udf_server.adapter.resolution import udf_to_binance_interval
from src.udf_server.config import (
    BINANCE_WS_URL,
    WS_PING_INTERVAL,
    WS_RECONNECT_BACKOFF,
    WS_RECONNECT_DELAY,
    WS_RECONNECT_MAX_DELAY,
    BAR_CACHE_MAX_BARS,
)
from src.udf_server.models.bar import Bar

logger = logging.getLogger(__name__)


class BinanceWsAdapter:
    """Maintains WebSocket connections to Binance for real-time kline updates.

    Subscribes on demand. Pushes updates into in-memory BarCache.
    Handles reconnection with exponential backoff.
    """

    def __init__(
        self,
        ws_url: str = BINANCE_WS_URL,
        reconnect_delay: float = WS_RECONNECT_DELAY,
        reconnect_max_delay: float = WS_RECONNECT_MAX_DELAY,
    ) -> None:
        self._ws_url = ws_url
        self._reconnect_delay = reconnect_delay
        self._reconnect_max_delay = reconnect_max_delay
        self._connection: ClientConnection | None = None
        self._subscriptions: dict[str, set[str]] = {}  # stream_name → {resolution, ...}
        self._bar_cache: dict[str, deque[Bar]] = {}  # stream_name → deque of bars
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def bar_cache(self) -> dict[str, deque[Bar]]:
        return self._bar_cache

    async def start(self) -> None:
        """Start the WebSocket listener task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Binance WebSocket adapter started")

    async def stop(self) -> None:
        """Stop the WebSocket listener and clean up."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._connection:
            await self._connection.close()
            self._connection = None
        logger.info("Binance WebSocket adapter stopped")

    def subscribe(self, symbol: str, resolution: str) -> None:
        """Subscribe to kline updates for a symbol+resolution.

        Subscription takes effect on next reconnection cycle.
        The stream name format is: <lowercase symbol>@kline_<interval>
        """
        try:
            interval = udf_to_binance_interval(resolution)
        except ValueError:
            return

        stream = f"{symbol.lower()}@kline_{interval}"
        if stream not in self._subscriptions:
            self._subscriptions[stream] = set()
            self._bar_cache[stream] = deque(maxlen=BAR_CACHE_MAX_BARS)
        self._subscriptions[stream].add(resolution)
        logger.debug("Subscribed to %s", stream)

    def unsubscribe(self, symbol: str, resolution: str) -> None:
        """Unsubscribe from a stream."""
        try:
            interval = udf_to_binance_interval(resolution)
        except ValueError:
            return

        stream = f"{symbol.lower()}@kline_{interval}"
        if stream in self._subscriptions:
            self._subscriptions[stream].discard(resolution)
            if not self._subscriptions[stream]:
                del self._subscriptions[stream]
                self._bar_cache.pop(stream, None)

    def get_bars(self, symbol: str, resolution: str) -> list[Bar]:
        """Get cached bars for a symbol+resolution."""
        try:
            interval = udf_to_binance_interval(resolution)
        except ValueError:
            return []
        stream = f"{symbol.lower()}@kline_{interval}"
        bars = self._bar_cache.get(stream, deque())
        return list(bars)

    async def _listen_loop(self) -> None:
        """Main loop: connect, subscribe, process messages, reconnect on failure."""
        delay = self._reconnect_delay

        while self._running:
            try:
                await self._connect_and_listen()
                # Clean disconnect — reset delay
                delay = self._reconnect_delay
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning(
                    "WebSocket disconnected, reconnecting in %.1fs", delay
                )
                await asyncio.sleep(delay)
                delay = min(delay * WS_RECONNECT_BACKOFF, self._reconnect_max_delay)

    async def _connect_and_listen(self) -> None:
        """Connect, send subscriptions, and process incoming messages."""
        async with websockets.connect(self._ws_url) as ws:
            self._connection = ws
            logger.info("Connected to Binance WebSocket: %s", self._ws_url)

            # Send subscription messages for all active streams
            streams = list(self._subscriptions.keys())
            if streams:
                await self._subscribe_streams(ws, streams)

            # Also subscribe to any new streams added while connecting
            new_streams = set(self._subscriptions.keys()) - set(streams)
            if new_streams:
                await self._subscribe_streams(ws, list(new_streams))

            # Message processing loop
            async for message in ws:
                await self._handle_message(message)

    async def _subscribe_streams(
        self,
        ws: ClientConnection,
        streams: list[str],
    ) -> None:
        """Send SUBSCRIBE messages for each stream."""
        # Binance allows combined streams: wss://.../stream?streams=stream1/stream2
        # But for per-stream subscriptions we use individual SUBSCRIBE messages
        for stream in streams:
            sub_msg = {
                "method": "SUBSCRIBE",
                "params": [stream],
                "id": id(stream) % (2**31),
            }
            await ws.send(json.dumps(sub_msg))
            logger.debug("Subscribed: %s", stream)

    async def _handle_message(self, raw: str) -> None:
        """Parse incoming kline message and update bar cache."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Handle subscription response — ignore
        if "result" in msg:
            return

        # Handle kline stream data
        stream = msg.get("stream", "")
        data = msg.get("data", {})

        if not stream or not data:
            return

        kline = data.get("k", {})
        if not kline:
            return

        is_final = kline.get("x", False)  # True = bar closed
        bar = Bar(
            time=int(kline["t"]) // 1000,  # ms → seconds
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
        )

        cache = self._bar_cache.get(stream)
        if cache is None:
            return

        if cache and cache[-1].time == bar.time:
            # Update current (in-progress) bar
            cache[-1] = bar
        else:
            cache.append(bar)

        if is_final:
            logger.debug(
                "Bar closed: %s %s @ %s",
                stream,
                kline.get("i", "?"),
                bar.time,
            )
