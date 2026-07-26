"""GET /symbols, GET /symbol_info — symbol resolution endpoints.

Supports both Binance crypto and ENTSO-E energy symbols.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from src.udf_server.models import LibrarySymbolInfo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["UDF"])


def _build_crypto_symbol_info(row: dict) -> dict:
    """Build a LibrarySymbolInfo dict from a Binance cache row."""
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


def _build_energy_symbol_info(es, currency: str = "EUR") -> dict:
    """Build a LibrarySymbolInfo dict for an energy bidding zone."""
    suffix = {"Day-ahead": "DA", "Intraday": "ID"}.get(es.contract_type, "??")
    return LibrarySymbolInfo(
        name=es.symbol,
        ticker=es.symbol,
        description=f"{es.display_name} — {es.contract_type} ({currency}/MWh)",
        type="energy",
        session="0900-1700",  # European power trading hours
        timezone="Europe/Berlin",
        exchange="ENTSO-E",
        listed_exchange="ENTSO-E",
        minmov=1,
        pricescale=100,
        has_intraday=True,
        has_daily=True,
        has_weekly_and_monthly=True,
        supported_resolutions=["15", "30", "60", "240", "1D", "1W", "1M"],
        intraday_multipliers=["15", "30", "60", "240"],
        volume_precision=0,
        data_status="streaming",
        format="price",
    ).model_dump()


@router.get("/symbols")
async def get_symbols(
    request: Request,
    symbol: str = Query(..., description="Ticker symbol (BTCUSDT or AREA_CODE:CONTRACT)"),
) -> dict:
    """Resolve a symbol — return full LibrarySymbolInfo."""
    # ─── Energy ───────────────────────────────────────────────
    if ":" in symbol:
        energy = request.app.state.energy
        es = energy.get_symbol(symbol.upper())
        if es is None:
            raise HTTPException(status_code=404, detail=f"Energy symbol not found: {symbol}")
        return _build_energy_symbol_info(es)

    # ─── Binance ──────────────────────────────────────────────
    store = request.app.state.symbol_store
    row = await store.get_symbol(symbol.upper())
    if row is None:
        logger.warning("Symbol not found: %s", symbol)
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")

    return _build_crypto_symbol_info(row)


@router.get("/symbol_info")
async def get_symbol_info(
    request: Request,
    symbol: str = Query(..., description="Ticker symbol"),
) -> dict:
    """Alias for /symbols."""
    return await get_symbols(request, symbol)
