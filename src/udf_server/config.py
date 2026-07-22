"""Single Source of Truth: all configuration for the UDF server.

Every constant here CAN be overridden by an environment variable of the same name.
Values are cast automatically: int, float, str. Booleans use "true"/"1".
This file = the canonical reference. .env = the override mechanism.
"""

from __future__ import annotations

import os


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(_env(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(_env(key, str(default)))


# ═══════════════════════════════════════════════════════════════════
# Server
# ═══════════════════════════════════════════════════════════════════

UDF_PORT: int = _env_int("UDF_PORT", 8088)
UDF_HOST: str = _env("UDF_HOST", "0.0.0.0")

# ═══════════════════════════════════════════════════════════════════
# UDF Protocol — resolution mapping
# ═══════════════════════════════════════════════════════════════════

RESOLUTION_TO_INTERVAL: dict[str, str] = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "120": "2h",
    "240": "4h",
    "360": "6h",
    "480": "8h",
    "720": "12h",
    "1D": "1d",
    "3D": "3d",
    "1W": "1w",
    "1M": "1M",
}

INTERVAL_TO_RESOLUTION: dict[str, str] = {v: k for k, v in RESOLUTION_TO_INTERVAL.items()}

SUPPORTED_RESOLUTIONS: list[str] = ["1", "5", "15", "60", "240", "1D", "1W", "1M"]
INTRADAY_MULTIPLIERS: list[str] = ["1", "5", "15", "60", "240"]

# ═══════════════════════════════════════════════════════════════════
# Binance REST API
# ═══════════════════════════════════════════════════════════════════

BINANCE_REST_URL: str = _env("BINANCE_REST_URL", "https://api.binance.com")
BINANCE_WS_URL: str = _env("BINANCE_WS_URL", "wss://stream.binance.com:9443/ws")
BINANCE_REQUEST_TIMEOUT: float = _env_float("BINANCE_REQUEST_TIMEOUT", 10.0)
BINANCE_MAX_KLINES_PER_REQUEST: int = _env_int("BINANCE_MAX_KLINES_PER_REQUEST", 1000)
BINANCE_RATE_LIMIT_RPM: int = _env_int("BINANCE_RATE_LIMIT_RPM", 1200)
BINANCE_MAX_RETRIES: int = _env_int("BINANCE_MAX_RETRIES", 3)

# ═══════════════════════════════════════════════════════════════════
# Symbol Cache (SQLite)
# ═══════════════════════════════════════════════════════════════════

SYMBOLS_DB_PATH: str = _env("SYMBOLS_DB_PATH", "data/symbols.db")
SYMBOL_SYNC_BATCH_SIZE: int = _env_int("SYMBOL_SYNC_BATCH_SIZE", 500)
SYMBOL_SEARCH_LIMIT: int = _env_int("SYMBOL_SEARCH_LIMIT", 100)

# ═══════════════════════════════════════════════════════════════════
# History endpoint
# ═══════════════════════════════════════════════════════════════════

DEFAULT_HISTORY_LIMIT: int = _env_int("DEFAULT_HISTORY_LIMIT", 500)
HISTORY_MAX_LIMIT: int = _env_int("HISTORY_MAX_LIMIT", 1000)

# ═══════════════════════════════════════════════════════════════════
# WebSocket Bridge
# ═══════════════════════════════════════════════════════════════════

WS_RECONNECT_DELAY: float = _env_float("WS_RECONNECT_DELAY", 1.0)
WS_RECONNECT_MAX_DELAY: float = _env_float("WS_RECONNECT_MAX_DELAY", 30.0)
WS_RECONNECT_BACKOFF: float = _env_float("WS_RECONNECT_BACKOFF", 2.0)
WS_PING_INTERVAL: float = _env_float("WS_PING_INTERVAL", 180.0)

# ═══════════════════════════════════════════════════════════════════
# Bar Cache (in-memory)
# ═══════════════════════════════════════════════════════════════════

BAR_CACHE_MAX_BARS: int = _env_int("BAR_CACHE_MAX_BARS", 2000)

# ═══════════════════════════════════════════════════════════════════
# Frontend
# ═══════════════════════════════════════════════════════════════════

FRONTEND_DIR: str = _env("FRONTEND_DIR", "")
