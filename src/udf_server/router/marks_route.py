"""GET /marks — chart event markers (stub, reserved for future work)."""

from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(tags=["UDF"])


@router.get("/marks")
async def get_marks(
    symbol: str = Query(..., description="Ticker symbol"),
    from_: int = Query(default=0, alias="from"),
    to: int = Query(default=0),
    resolution: str = Query(default="1D"),
) -> dict:
    """Return chart event markers (news, dividends, etc.).

    Currently returns empty — reserved for future implementation.
    """
    return {
        "id": [],
        "time": [],
        "color": [],
        "text": [],
        "label": [],
        "labelFontColor": [],
        "minSize": [],
    }
