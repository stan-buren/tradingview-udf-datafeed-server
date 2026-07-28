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


# ── Resolution → seconds ──────────────────────────────────────

_RESOLUTION_SECONDS: dict[str, int] = {
    "1": 60,
    "5": 300,
    "15": 900,
    "30": 1800,
    "60": 3600,
    "120": 7200,
    "240": 14400,
    "360": 21600,
    "480": 28800,
    "720": 43200,
    "1D": 86400,
    "3D": 259200,
    "1W": 604800,
    "1M": 2592000,
}


def resolution_to_seconds(resolution: str) -> int:
    """Convert a UDF resolution string to duration in seconds."""
    if resolution not in _RESOLUTION_SECONDS:
        raise ValueError(f"Unknown resolution: {resolution!r}")
    return _RESOLUTION_SECONDS[resolution]
