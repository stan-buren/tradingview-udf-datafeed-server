"""GET /history — historical OHLCV bars (core data endpoint).

Supports both Binance crypto and ENTSO-E energy symbols.
Energy symbols use format: AREA_CODE:CONTRACT (e.g. 10Y1001A1001A82H:DA).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from src.udf_server.adapter.resolution import is_valid_resolution
from src.udf_server.config import DEFAULT_HISTORY_LIMIT, HISTORY_MAX_LIMIT
from src.udf_server.models.bar import HistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["UDF"])

# Energy resolutions: intraday starts from 15min (Parquet data is 15-60min native)
ENERGY_RESOLUTIONS = {"15", "30", "60", "240", "1D", "1W", "1M"}


def _is_energy_symbol(symbol: str) -> bool:
    """Energy symbols contain ':' separator (e.g. '10Y1001A1001A82H:DA')."""
    return ":" in symbol


@router.get("/history")
async def get_history(
    request: Request,
    symbol: str = Query(..., description="Ticker symbol (BTCUSDT or AREA_CODE:CONTRACT)"),
    resolution: str = Query(..., description="Bar resolution, e.g. '60' for 1h"),
    from_: int = Query(default=0, alias="from", description="From timestamp (seconds)"),
    to: int = Query(default=0, description="To timestamp (seconds)"),
    countback: int = Query(default=0, description="Number of bars back from 'to'"),
) -> dict:
    """Return historical OHLCV bars in UDF columnar format."""
    if not is_valid_resolution(resolution):
        raise HTTPException(status_code=400, detail=f"Unsupported resolution: {resolution}")

    limit = min(countback if countback > 0 else DEFAULT_HISTORY_LIMIT, HISTORY_MAX_LIMIT)

    # ─── Energy mode ──────────────────────────────────────────
    if _is_energy_symbol(symbol):
        if resolution not in ENERGY_RESOLUTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Energy data supports resolutions: {', '.join(sorted(ENERGY_RESOLUTIONS))}",
            )

        energy = request.app.state.energy
        try:
            bars = energy.get_bars(
                symbol=symbol.upper(),
                resolution=resolution,
                from_time=from_ if from_ > 0 else None,
                to_time=to if to > 0 else None,
                count_back=limit,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            logger.exception("Energy query failed for %s/%s", symbol, resolution)
            return HistoryResponse.error(str(e)).__dict__

        if not bars:
            return HistoryResponse.no_data().__dict__
        return HistoryResponse.from_bars(bars).__dict__

    # ─── Binance mode ─────────────────────────────────────────
    store = request.app.state.symbol_store
    if not await store.get_symbol(symbol.upper()):
        raise HTTPException(status_code=404, detail=f"Symbol not found: {symbol}")

    adapter = request.app.state.binance_rest
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
        return HistoryResponse.from_bars([]).__dict__
    return HistoryResponse.from_bars(bars).__dict__
