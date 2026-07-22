"""GET /search — symbol search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.udf_server.config import SYMBOL_SEARCH_LIMIT
from src.udf_server.models import SearchResultItem

router = APIRouter(tags=["UDF"])


@router.get("/search")
async def search_symbols(
    request: Request,
    query: str = Query(default="", description="Search query"),
    type: str = Query(default="", description="Symbol type filter"),
    exchange: str = Query(default="", description="Exchange filter"),
    limit: int = Query(default=30, description="Max results"),
) -> list[dict]:
    """Search for symbols matching the query.

    Called as user types in the chart's symbol search box.
    Returns array of SearchResultItem objects.
    """
    store = request.app.state.symbol_store
    limit = min(limit, SYMBOL_SEARCH_LIMIT)

    rows = await store.search_symbols(query, limit=limit)

    results: list[dict] = []
    for row in rows:
        symbol = row["symbol"]
        base = row.get("base_asset", symbol.replace("USDT", ""))
        item = SearchResultItem(
            symbol=symbol,
            full_name=symbol,
            description=f"{base} / TetherUS",
            exchange=row.get("quote_asset", "Binance"),
            ticker=symbol,
            type="crypto",
        )

        # Apply optional filters
        if type and item.type != type:
            continue
        if exchange and item.exchange != exchange:
            continue

        results.append(item.model_dump())

    return results
