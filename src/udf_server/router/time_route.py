"""GET /time — server time endpoint for clock drift detection."""

from __future__ import annotations

import time

from fastapi import APIRouter

router = APIRouter(tags=["UDF"])


@router.get("/time")
async def get_time() -> int:
    """Return current Unix timestamp in seconds.

    The chart widget uses this to detect clock drift between
    client and server.
    """
    return int(time.time())
