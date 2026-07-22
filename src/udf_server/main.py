"""FastAPI application — entry point for the UDF datafeed server."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.udf_server.adapter.binance_rest import BinanceRestAdapter
from src.udf_server.adapter.binance_ws import BinanceWsAdapter
from src.udf_server.cache.bar_cache import BarCache
from src.udf_server.cache.symbol_store import SymbolStore
from src.udf_server import config
from src.udf_server.router import (
    config_route,
    history_route,
    marks_route,
    search_route,
    symbols_route,
    time_route,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(config.FRONTEND_DIR or (Path(__file__).resolve().parent.parent.parent / "frontend").as_posix())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to Binance, sync symbols, start WebSocket.

    Shutdown: close connections gracefully.
    """
    logger.info("Starting UDF server...")

    # Initialize caches
    app.state.bar_cache = BarCache()

    # Initialize symbol store
    app.state.symbol_store = SymbolStore()
    await app.state.symbol_store.__aenter__()
    count = await app.state.symbol_store.count()
    logger.info("Symbol cache initialized (%d symbols)", count)

    # Initialize Binance REST adapter
    app.state.binance_rest = BinanceRestAdapter()
    await app.state.binance_rest.__aenter__()

    # Initialize WebSocket adapter (background task)
    app.state.binance_ws = BinanceWsAdapter()
    await app.state.binance_ws.start()

    logger.info("UDF server ready on %s:%d", config.UDF_HOST, config.UDF_PORT)

    yield

    # Shutdown
    logger.info("Shutting down UDF server...")
    await app.state.binance_ws.stop()
    await app.state.binance_rest.__aexit__(None, None, None)
    await app.state.symbol_store.__aexit__(None, None, None)
    logger.info("Shutdown complete")


app = FastAPI(
    title="TradingView UDF Datafeed Server",
    description="Python/FastAPI implementation of the TradingView UDF protocol. "
    "Bridges Binance public market data to TradingView-compatible charts.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow any origin for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── UDF Protocol Routes ──────────────────────────────────────

app.include_router(config_route.router)
app.include_router(time_route.router)
app.include_router(symbols_route.router)
app.include_router(search_route.router)
app.include_router(history_route.router)
app.include_router(marks_route.router)


# ─── Frontend Demo ────────────────────────────────────────────

@app.get("/demo")
async def demo_redirect():
    """Redirect to the static demo page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/demo/index.html")


if FRONTEND_DIR.exists():
    app.mount("/demo", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="demo")


# ─── Health Check ─────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    store = app.state.symbol_store
    return {
        "status": "ok",
        "symbols_cached": await store.count(),
        "bar_cache_keys": app.state.bar_cache.stats()["keys"],
    }
