"""Tests for Binance REST adapter — kline parsing and format conversion."""

import pytest

from src.udf_server.adapter.binance_rest import BinanceRestAdapter


class TestParseKlines:
    """Unit tests for _parse_klines — doesn't need network."""

    def test_valid_klines(self, mock_binance_klines_response: list[list]) -> None:
        adapter = BinanceRestAdapter()
        bars = adapter._parse_klines(mock_binance_klines_response)

        assert len(bars) == 3

        # First bar
        assert bars[0].time == 1710374400  # ms → seconds
        assert bars[0].open == 42050.00
        assert bars[0].high == 42180.00
        assert bars[0].low == 42000.00
        assert bars[0].close == 42100.50
        assert bars[0].volume == 1250.4

        # Timestamps are ascending
        assert bars[0].time < bars[1].time < bars[2].time

    def test_empty_klines(self) -> None:
        adapter = BinanceRestAdapter()
        bars = adapter._parse_klines([])
        assert bars == []

    def test_single_kline(self) -> None:
        adapter = BinanceRestAdapter()
        raw = [[
            1710374400000, "100.0", "105.0", "99.0",
            "102.0", "500.0", 1710377999999, "51000.0",
            100, "250.0", "25500.0", "0",
        ]]
        bars = adapter._parse_klines(raw)
        assert len(bars) == 1
        assert bars[0].time == 1710374400
        assert bars[0].close == 102.0

    def test_timestamp_conversion_ms_to_seconds(self) -> None:
        """Ensure Binance ms timestamps become Unix seconds."""
        adapter = BinanceRestAdapter()
        # 2024-01-01 00:00:00 in ms
        raw = [[
            1704067200000, "100.0", "100.0", "100.0",
            "100.0", "0.0", 1704067259999, "0.0",
            0, "0.0", "0.0", "0",
        ]]
        bars = adapter._parse_klines(raw)
        assert bars[0].time == 1704067200  # 2024-01-01 00:00:00 in seconds
