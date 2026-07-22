"""SQLite symbol cache — stores Binance trading pairs for fast lookup."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import aiosqlite

from src.udf_server.config import SYMBOLS_DB_PATH

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS symbols (
    symbol      TEXT PRIMARY KEY,
    base_asset  TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'TRADING',
    pricescale  INTEGER NOT NULL DEFAULT 100,
    minmov      INTEGER NOT NULL DEFAULT 1,
    tick_size   TEXT NOT NULL DEFAULT '0.01'
);

CREATE INDEX IF NOT EXISTS idx_symbols_symbol
    ON symbols(symbol);

CREATE INDEX IF NOT EXISTS idx_symbols_base
    ON symbols(base_asset);

CREATE INDEX IF NOT EXISTS idx_symbols_quote
    ON symbols(quote_asset);
"""


class SymbolStore:
    """Async SQLite store for Binance trading symbol metadata.

    Populated once at startup from /api/v3/exchangeInfo.
    Read-only at runtime — no write contention.
    """

    def __init__(self, db_path: str = SYMBOLS_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None

    async def __aenter__(self) -> SymbolStore:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._init_schema()
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SymbolStore not entered. Use 'async with'.")
        return self._db

    async def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        await self.db.executescript(CREATE_TABLE_SQL)
        await self.db.commit()

    # ─── Write (startup sync) ─────────────────────────────────

    async def upsert_symbols(
        self,
        symbols: list[dict[str, str | int]],
    ) -> int:
        """Insert or update symbol records. Returns count of affected rows.

        Each dict must have: symbol, base_asset, quote_asset, status.
        Optional: pricescale (default 100), minmov (default 1).
        """
        # Ensure required keys are always present (executemany requires all bound params)
        for s in symbols:
            s.setdefault("pricescale", 100)
            s.setdefault("minmov", 1)

        sql = """
        INSERT INTO symbols (symbol, base_asset, quote_asset, status, pricescale, minmov)
        VALUES (:symbol, :base_asset, :quote_asset, :status, :pricescale, :minmov)
        ON CONFLICT(symbol) DO UPDATE SET
            base_asset = excluded.base_asset,
            quote_asset = excluded.quote_asset,
            status = excluded.status,
            pricescale = excluded.pricescale,
            minmov = excluded.minmov
        """
        cursor = await self.db.executemany(sql, symbols)
        await self.db.commit()
        return cursor.rowcount

    async def clear(self) -> None:
        """Remove all symbols (before re-sync)."""
        await self.db.execute("DELETE FROM symbols")
        await self.db.commit()

    # ─── Read (runtime) ───────────────────────────────────────

    async def get_symbol(self, symbol: str) -> dict | None:
        """Look up a single symbol by ticker (e.g. 'BTCUSDT')."""
        cursor = await self.db.execute(
            "SELECT * FROM symbols WHERE symbol = ? AND status = 'TRADING'",
            (symbol.upper(),),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def search_symbols(
        self,
        query: str,
        limit: int = 50,
    ) -> list[dict]:
        """Search symbols by name (prefix + substring match)."""
        pattern = f"%{query.upper()}%"
        cursor = await self.db.execute(
            "SELECT * FROM symbols "
            "WHERE status = 'TRADING' AND (symbol LIKE ? OR base_asset LIKE ?) "
            "ORDER BY "
            "  CASE WHEN symbol = ? THEN 0 "
            "       WHEN symbol LIKE ? THEN 1 "
            "       ELSE 2 END, "
            "  symbol "
            "LIMIT ?",
            (pattern, pattern, query.upper(), f"{query.upper()}%", limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def count(self) -> int:
        """Count total symbols in cache."""
        cursor = await self.db.execute("SELECT COUNT(*) FROM symbols")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_all_symbols(self) -> list[str]:
        """Get all active symbol names."""
        cursor = await self.db.execute(
            "SELECT symbol FROM symbols WHERE status = 'TRADING' ORDER BY symbol"
        )
        rows = await cursor.fetchall()
        return [row["symbol"] for row in rows]

    # ─── Sync (CLI entry point) ───────────────────────────────

    async def sync_from_binance(self, exchange_info: dict) -> int:
        """Parse Binance /api/v3/exchangeInfo and populate the cache.

        Filters: only SPOT market, TRADING status, USDT quote pairs.

        Returns count of symbols synced.
        """
        symbols_data: list[dict] = []

        for s in exchange_info.get("symbols", []):
            if (
                s.get("status") != "TRADING"
                or s.get("quoteAsset") != "USDT"
                or s.get("isSpotTradingAllowed") is not True
            ):
                continue

            # Determine pricescale from tick size
            tick_size_str = next(
                (f.get("tickSize", "0.01")
                 for f in s.get("filters", [])
                 if f.get("filterType") == "PRICE_FILTER"),
                "0.01",
            )
            try:
                tick_size = float(tick_size_str)
            except ValueError:
                tick_size = 0.01

            # pricescale: 10^decimal_places_of_tick_size
            # e.g. tick 0.01 → pricescale 100, tick 0.001 → 1000
            pricescale = 100
            if tick_size < 1:
                decimals = len(tick_size_str.split(".")[-1].rstrip("0"))
                pricescale = 10 ** max(decimals, 2)

            symbols_data.append({
                "symbol": s["symbol"],
                "base_asset": s["baseAsset"],
                "quote_asset": s["quoteAsset"],
                "status": s["status"],
                "pricescale": pricescale,
                "minmov": 1,
            })

        await self.clear()
        count = await self.upsert_symbols(symbols_data)
        logger.info("Synced %d USDT spot symbols to %s", count, self._db_path)
        return count
