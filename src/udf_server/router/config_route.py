"""GET /config — returns datafeed capabilities."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.udf_server.config import (
    INTRADAY_MULTIPLIERS,
    SUPPORTED_RESOLUTIONS,
)
from src.udf_server.models import DatafeedConfiguration, Exchange, SymbolType

router = APIRouter(tags=["UDF"])


@router.get("/config")
async def get_config(request: Request) -> dict:
    """Return UDF datafeed configuration.

    This is the first call the chart widget makes.
    Tells the client which resolutions, exchanges, and symbol types are available.
    """
    cfg = DatafeedConfiguration(
        supported_resolutions=SUPPORTED_RESOLUTIONS,
        supports_search=True,
        supports_group_request=False,
        supports_marks=False,
        supports_timescale_marks=True,
        exchanges=[
            Exchange(
                value="Binance",
                name="Binance",
                desc="Binance Spot",
            ),
            Exchange(
                value="ENTSO-E",
                name="ENTSO-E",
                desc="European Energy Prices",
            ),
        ],
        symbols_types=[
            SymbolType(name="crypto", value="crypto"),
            SymbolType(name="energy", value="energy"),
        ],
        intraday_multipliers=INTRADAY_MULTIPLIERS,
    )
    return cfg.model_dump()
