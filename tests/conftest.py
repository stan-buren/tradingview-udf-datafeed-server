"""Test fixtures: mock Binance API, test client, test database."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_binance_klines_response() -> list[list]:
    """Standard Binance kline response for BTCUSDT 1h."""
    return [
        [
            1710374400000,  # Open time (ms)
            "42050.00",     # Open
            "42180.00",     # High
            "42000.00",     # Low
            "42100.50",     # Close
            "1250.4",       # Volume
            1710377999999,  # Close time
            "52650000.0",   # Quote volume
            1240,           # Trades
            "620.1",        # Taker buy volume
            "26100000.0",   # Taker buy quote volume
            "0",            # Ignore
        ],
        [
            1710378000000,
            "42100.50",
            "42200.00",
            "42080.00",
            "42150.30",
            "980.2",
            1710381599999,
            "41300000.0",
            980,
            "490.1",
            "20650000.0",
            "0",
        ],
        [
            1710381600000,
            "42150.30",
            "42190.00",
            "42050.00",
            "42080.10",
            "1100.7",
            1710385199999,
            "46300000.0",
            1100,
            "550.3",
            "23150000.0",
            "0",
        ],
    ]


@pytest.fixture
def mock_binance_exchange_info() -> dict:
    """Simplified Binance exchangeInfo response."""
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01",
                    },
                ],
            },
            {
                "symbol": "ETHUSDT",
                "status": "TRADING",
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01",
                    },
                ],
            },
            {
                "symbol": "SOLUSDT",
                "status": "TRADING",
                "baseAsset": "SOL",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.001",
                    },
                ],
            },
            # Non-USDT pair — should be skipped by symbol sync
            {
                "symbol": "BTCBUSD",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "BUSD",
                "isSpotTradingAllowed": True,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                ],
            },
            # Not trading — should be skipped
            {
                "symbol": "XRPUSDT",
                "status": "BREAK",
                "baseAsset": "XRP",
                "quoteAsset": "USDT",
                "isSpotTradingAllowed": True,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.0001"},
                ],
            },
        ],
    }
