"""GET /history — historical OHLCV bars (the core data endpoint)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from src.udf_server.adapter.resolution import is_valid_resolution
from src.udf_server.config import DEFAULT_HISTORY_LIMIT, HISTORY_MAX_LIMIT
from src.udf_server.models.bar import HistoryResponse
logger = logging.getLogger(__name__)

router = APIRouter(tags=["UDF"])


@router.get("/history")
async def get_history(
    request: Request,
    symbol: str = Query(..., description="Ticker symbol, e.g. BTCUSDT"),
    resolution: str = Query(..., description="Bar resolution, e.g. '60' for 1h"),
    from_: int = Query(default=0, alias="from", description="From timestamp (seconds)"),
    to: int = Query(default=0, description="To timestamp (seconds)"),
    countback: int = Query(default=0, description="Number of bars back from 'to'"),
) -> dict:
    """Return historical OHLCV bars in UDF columnar format.

    Edge cases handled:
    - countback takes priority over from_
    - missing symbol → 404
    - no data in range → s: "no_data" + nextTime
    - unsupported resolution → 400
    """
    # Validate resolution
    if not is_valid_resolution(resolution):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported resolution: {resolution}",
        )

    # Validate symbol
    store = request.app.state.symbol_store
    if not await store.get_symbol(symbol.upper()):
        raise HTTPException(
            status_code=404,
            detail=f"Symbol not found: {symbol}",
        )

    adapter = request.app.state.binance_rest
    limit = min(countback if countback > 0 else DEFAULT_HISTORY_LIMIT, HISTORY_MAX_LIMIT)
    start_time = None if countback > 0 else from_ if from_ > 0 else None
    end_time = to if to > 0 else None
    try:
        bars = await adapter.fetch_klines(
            symbol=symbol,
            resolution=resolution,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to fetch klines for %s/%s", symbol, resolution)
        return HistoryResponse.error(str(e)).__dict__

    if not bars:
        # For 24/7 crypto, no bars → empty "ok", not "no_data"
        return HistoryResponse.from_bars([]).__dict__
    return HistoryResponse.from_bars(bars).__dict__
