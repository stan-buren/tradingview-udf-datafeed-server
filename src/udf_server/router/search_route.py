"""GET /search — symbol search endpoint.

Supports both Binance crypto and ENTSO-E energy symbols.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.udf_server.config import SYMBOL_SEARCH_LIMIT
from src.udf_server.models import SearchResultItem

router = APIRouter(tags=["UDF"])


@router.get("/search")
async def search_symbols(
    request: Request,
    query: str = Query(default="", description="Search query"),
    type: str = Query(default="", description="Symbol type filter (crypto/energy)"),
    exchange: str = Query(default="", description="Exchange filter"),
    limit: int = Query(default=30, description="Max results"),
) -> list[dict]:
    """Search symbols across Binance + Energy."""
    limit = min(limit, SYMBOL_SEARCH_LIMIT)
    results: list[dict] = []

    # ─── Energy search ────────────────────────────────────────
    energy = request.app.state.energy
    energy_limit = limit if type == "energy" else 10
    for es in energy.search_symbols(query, limit=energy_limit):
        if type and type != "energy":
            continue
        results.append(SearchResultItem(
            symbol=es.symbol,
            full_name=es.symbol,
            description=f"{es.display_name} — {es.contract_type}",
            exchange="ENTSO-E",
            ticker=es.symbol,
            type="energy",
        ).model_dump())

    # ─── Binance search ───────────────────────────────────────
    if not type or type == "crypto":
        store = request.app.state.symbol_store
        rows = await store.search_symbols(query, limit=max(5, limit - len(results)))
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
            results.append(item.model_dump())

    return results[:limit]
