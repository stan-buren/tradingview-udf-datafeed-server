"""Tests for resolution mapping between UDF and Binance formats."""

import pytest

from src.udf_server.adapter.resolution import (
    binance_to_udf_resolution,
    is_valid_resolution,
    udf_to_binance_interval,
)


class TestUdfToBinance:
    def test_standard_resolutions(self) -> None:
        assert udf_to_binance_interval("1") == "1m"
        assert udf_to_binance_interval("5") == "5m"
        assert udf_to_binance_interval("15") == "15m"
        assert udf_to_binance_interval("60") == "1h"
        assert udf_to_binance_interval("240") == "4h"
        assert udf_to_binance_interval("1D") == "1d"
        assert udf_to_binance_interval("1W") == "1w"
        assert udf_to_binance_interval("1M") == "1M"

    def test_unknown_resolution_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported resolution"):
            udf_to_binance_interval("999")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            udf_to_binance_interval("")


class TestBinanceToUdf:
    def test_standard_intervals(self) -> None:
        assert binance_to_udf_resolution("1m") == "1"
        assert binance_to_udf_resolution("5m") == "5"
        assert binance_to_udf_resolution("1h") == "60"
        assert binance_to_udf_resolution("1d") == "1D"
        assert binance_to_udf_resolution("1w") == "1W"

    def test_unknown_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown Binance interval"):
            binance_to_udf_resolution("2y")


class TestIsValidResolution:
    def test_valid(self) -> None:
        assert is_valid_resolution("1") is True
        assert is_valid_resolution("60") is True
        assert is_valid_resolution("1D") is True

    def test_invalid(self) -> None:
        assert is_valid_resolution("") is False
        assert is_valid_resolution("xyz") is False
        assert is_valid_resolution("1m") is False  # Binance interval, not UDF
