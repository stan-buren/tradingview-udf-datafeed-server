"""GET /symbols, GET /symbol_info — symbol resolution endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from src.udf_server.models import LibrarySymbolInfo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["UDF"])


def _build_symbol_info(row: dict) -> dict:
    """Build a LibrarySymbolInfo dict from a cache row."""
    symbol = row["symbol"]
    base = row.get("base_asset", symbol.replace("USDT", ""))
    pricescale = row.get("pricescale", 100)

    return LibrarySymbolInfo(
        name=symbol,
        ticker=symbol,
        description=f"{base} / TetherUS",
        type="crypto",
        session="24x7",
        timezone="Etc/UTC",
        exchange="Binance",
        listed_exchange="Binance",
        minmov=row.get("minmov", 1),
        pricescale=pricescale,
        has_intraday=True,
        has_daily=True,
        has_weekly_and_monthly=True,
        supported_resolutions=["1", "5", "15", "60", "240", "1D", "1W", "1M"],
        intraday_multipliers=["1", "5", "15", "60", "240"],
        volume_precision=8,
        data_status="streaming",
        format="price",
    ).model_dump()


@router.get("/symbols")
async def get_symbols(
    request: Request,
    symbol: str = Query(..., description="Ticker symbol, e.g. BTCUSDT"),
) -> dict:
    """Resolve a symbol — return full LibrarySymbolInfo.

    Called when user selects a symbol in the chart widget.
    """
    store = request.app.state.symbol_store
    row = await store.get_symbol(symbol.upper())
    if row is None:
        logger.warning("Symbol not found: %s", symbol)
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")

    return _build_symbol_info(row)


@router.get("/symbol_info")
async def get_symbol_info(
    request: Request,
    symbol: str = Query(..., description="Ticker symbol"),
) -> dict:
    """Alias for /symbols — some UDF clients use this path."""
    return await get_symbols(request, symbol)
