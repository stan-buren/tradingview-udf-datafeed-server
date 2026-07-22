"""Tests for SQLite symbol cache."""

import pytest

from src.udf_server.cache.symbol_store import SymbolStore


@pytest.fixture
async def store() -> SymbolStore:
    """In-memory SQLite store for testing."""
    s = SymbolStore(db_path=":memory:")
    await s.__aenter__()
    yield s
    await s.__aexit__(None, None, None)


class TestSymbolStore:
    async def test_init_creates_table(self, store: SymbolStore) -> None:
        """Schema is created on init."""
        cursor = await store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='symbols'"
        )
        row = await cursor.fetchone()
        assert row is not None

    async def test_upsert_and_get(self, store: SymbolStore) -> None:
        symbols = [
            {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT", "status": "TRADING"},
            {"symbol": "ETHUSDT", "base_asset": "ETH", "quote_asset": "USDT", "status": "TRADING"},
        ]
        count = await store.upsert_symbols(symbols)
        assert count == 2

        row = await store.get_symbol("BTCUSDT")
        assert row is not None
        assert row["symbol"] == "BTCUSDT"
        assert row["base_asset"] == "BTC"

    async def test_get_nonexistent(self, store: SymbolStore) -> None:
        row = await store.get_symbol("NONEXISTENT")
        assert row is None

    async def test_search_symbols(self, store: SymbolStore) -> None:
        symbols = [
            {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT", "status": "TRADING"},
            {"symbol": "ETHUSDT", "base_asset": "ETH", "quote_asset": "USDT", "status": "TRADING"},
            {"symbol": "BTCUSDC", "base_asset": "BTC", "quote_asset": "USDC", "status": "TRADING"},
        ]
        await store.upsert_symbols(symbols)

        results = await store.search_symbols("BTC", limit=10)
        assert len(results) == 2  # BTCUSDT, BTCUSDC

        results = await store.search_symbols("ETH", limit=10)
        assert len(results) == 1

    async def test_non_trading_symbol_not_returned(self, store: SymbolStore) -> None:
        symbols = [
            {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT", "status": "BREAK"},
        ]
        await store.upsert_symbols(symbols)

        # get_symbol filters by status='TRADING'
        row = await store.get_symbol("BTCUSDT")
        assert row is None

    async def test_count(self, store: SymbolStore) -> None:
        assert await store.count() == 0

        symbols = [
            {"symbol": "AUSDT", "base_asset": "A", "quote_asset": "USDT", "status": "TRADING"},
        ]
        await store.upsert_symbols(symbols)
        assert await store.count() == 1

    async def test_clear(self, store: SymbolStore) -> None:
        symbols = [
            {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT", "status": "TRADING"},
        ]
        await store.upsert_symbols(symbols)
        assert await store.count() == 1

        await store.clear()
        assert await store.count() == 0

    async def test_sync_from_binance(self, store: SymbolStore, mock_binance_exchange_info: dict) -> None:
        count = await store.sync_from_binance(mock_binance_exchange_info)
        # Only TRADING + USDT pairs should be synced (BTCUSDT, ETHUSDT, SOLUSDT)
        # BTCBUSD is BUSD, XRPUSDT is BREAK → both skipped
        assert count == 3

        all_symbols = await store.get_all_symbols()
        assert "BTCUSDT" in all_symbols
        assert "ETHUSDT" in all_symbols
        assert "SOLUSDT" in all_symbols
        assert "BTCBUSD" not in all_symbols
        assert "XRPUSDT" not in all_symbols
