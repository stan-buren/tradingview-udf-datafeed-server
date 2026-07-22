from __future__ import annotations

from src.udf_server.config import (
    INTERVAL_TO_RESOLUTION,
    RESOLUTION_TO_INTERVAL,
    SUPPORTED_RESOLUTIONS,
)


def udf_to_binance_interval(resolution: str) -> str:
    """Convert UDF resolution string to Binance kline interval.

    Raises ValueError if resolution is not supported.
    """
    if resolution not in RESOLUTION_TO_INTERVAL:
        raise ValueError(
            f"Unsupported resolution: {resolution!r}. "
            f"Supported: {SUPPORTED_RESOLUTIONS}"
        )
    return RESOLUTION_TO_INTERVAL[resolution]


def binance_to_udf_resolution(interval: str) -> str:
    """Convert Binance kline interval to UDF resolution string.

    Raises ValueError if interval is unknown.
    """
    if interval not in INTERVAL_TO_RESOLUTION:
        raise ValueError(f"Unknown Binance interval: {interval!r}")
    return INTERVAL_TO_RESOLUTION[interval]


def is_valid_resolution(resolution: str) -> bool:
    """Check whether a UDF resolution string is supported."""
    return resolution in RESOLUTION_TO_INTERVAL
