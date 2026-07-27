"""Energy data adapter — reads ENTSO-E prices from Iceberg Parquet via PyArrow + DuckDB.

PyArrow handles S3 I/O (boto3 → SeaweedFS). DuckDB handles analytical queries (OHLCV).
Each bidding zone + contract type = one TradingView "symbol".

Symbol format: AREA_CODE:CONTRACT (e.g. "10Y1001A1001A82H:DA")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import boto3
import duckdb

from src.udf_server.config import (
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_SECRET_KEY,
)
from src.udf_server.models.bar import Bar

logger = logging.getLogger(__name__)

# UDF resolution → DuckDB date_trunc period
_RESOLUTION_TO_PERIOD: dict[str, str] = {
    "1": "minute",
    "5": "minute",
    "15": "minute",
    "30": "minute",
    "60": "hour",
    "240": "hour",
    "1D": "day",
    "1W": "week",
    "1M": "month",
}

_SUPPORTED_RESOLUTIONS = ["15", "30", "60", "240", "1D", "1W", "1M"]

# Parquet data prefix on S3
_PARQUET_PREFIX = "staging/energyprices_12_1_d_r3/data/"


@dataclass(frozen=True, slots=True)
class EnergySymbol:
    """Represents an energy bidding zone + contract type."""

    area_code: str
    display_name: str
    contract_type: str
    symbol: str  # e.g. "10Y1001A1001A82H:DA"


class EnergyAdapter:
    """Reads ENTSO-E price data from Iceberg Parquet via boto3 + DuckDB.

    PyArrow reads Parquet from SeaweedFS S3 into temporary local files.
    DuckDB queries the cached files for OHLCV aggregation.
    """

    PARQUET_GLOB = f"s3://{S3_BUCKET}/{_PARQUET_PREFIX}*.parquet"

    def __init__(self) -> None:
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._symbols: list[EnergySymbol] | None = None
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            endpoint_url=f"http://{S3_ENDPOINT}",
            region_name="us-east-1",
        )
        self._local_dir = Path("/tmp/energy_parquet_cache")
        self._local_dir.mkdir(parents=True, exist_ok=True)

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(":memory:")
        try:
            self._conn.execute("SELECT 1")
        except Exception:
            self._conn = duckdb.connect(":memory:")
        return self._conn

    # ─── S3 I/O via boto3 ────────────────────────────────────

    def _download_parquet_files(self) -> list[Path]:
        """Download Parquet files from S3 to local cache. Returns paths."""
        if hasattr(self, '_cached_paths') and self._cached_paths:
            return self._cached_paths
        paths = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=_PARQUET_PREFIX):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if not key.endswith(".parquet"):
                    continue
                local_path = self._local_dir / Path(key).name
                if not local_path.exists():
                    logger.debug("Downloading %s → %s", key, local_path)
                    self._s3.download_file(S3_BUCKET, key, str(local_path))
                paths.append(local_path)
        self._cached_paths = paths
        return paths

    # ─── Symbol management ────────────────────────────────────

    def load_symbols(self) -> list[EnergySymbol]:
        """Load distinct bidding zones from Parquet. Cached in memory."""
        if self._symbols is not None:
            return self._symbols

        logger.info("Downloading Parquet files for symbol discovery...")
        paths = self._download_parquet_files()
        if not paths:
            logger.warning("No Parquet files found in S3")
            return []

        # Read all files into DuckDB and get distinct zones
        file_list = ", ".join(f"'{p}'" for p in paths)
        logger.info("Loading %d Parquet files into DuckDB...", len(paths))
        rows = self.conn.execute(f"""
            SELECT DISTINCT area_code, area_display_name, contract_type
            FROM read_parquet([{file_list}])
            ORDER BY area_display_name, contract_type
        """).fetchall()

        symbols: list[EnergySymbol] = []
        for row in rows:
            area_code = row[0]
            display_name = row[1] or area_code
            contract = {"Day-ahead": "DA", "Intraday": "ID"}.get(row[2], row[2][:2].upper())
            symbol_id = f"{area_code}:{contract}"
            symbols.append(EnergySymbol(
                area_code=area_code,
                display_name=display_name,
                contract_type=row[2],
                symbol=symbol_id,
            ))

        self._symbols = symbols
        logger.info("Loaded %d energy symbols", len(symbols))
        return symbols

    def get_symbol(self, symbol: str) -> EnergySymbol | None:
        """Look up an energy symbol by ID (case-insensitive)."""
        symbol_upper = symbol.upper()
        for s in self.load_symbols():
            if s.symbol.upper() == symbol_upper:
                return s
        return None

    def search_symbols(self, query: str, limit: int = 30) -> list[EnergySymbol]:
        """Search energy symbols by display name or area code."""
        q = query.upper()
        results = []
        for s in self.load_symbols():
            if q in s.display_name.upper() or q in s.area_code.upper() or q in s.symbol:
                results.append(s)
                if len(results) >= limit:
                    break
        return results

    # ─── OHLCV query ──────────────────────────────────────────

    def get_bars(
        self,
        symbol: str,
        resolution: str,
        *,
        from_time: int | None = None,
        to_time: int | None = None,
        count_back: int = 300,
    ) -> list[Bar]:
        """Fetch OHLCV bars for an energy symbol from cached Parquet files."""
        energy = self.get_symbol(symbol)
        if energy is None:
            raise ValueError(f"Unknown energy symbol: {symbol}")

        period = _RESOLUTION_TO_PERIOD.get(resolution, "hour")

        # Ensure cache is populated
        paths = self._download_parquet_files()
        file_list = ", ".join(f"'{p}'" for p in paths)

        # Build time filter
        time_filter = ""
        if to_time and to_time > 0:
            time_filter += f" AND epoch_ms(date_time_utc) <= {to_time * 1000}"
        if from_time and from_time > 0:
            time_filter += f" AND epoch_ms(date_time_utc) >= {from_time * 1000}"

        bucket_expr = f"date_trunc('{period}', date_time_utc)"

        sql = f"""
            WITH raw AS (
                SELECT date_time_utc, \"price_currency_x2Fm_wh\" AS price_eur_mwh
                FROM read_parquet([{file_list}])
                WHERE area_code = '{energy.area_code}'
                  AND contract_type = '{energy.contract_type}'
                  AND "price_currency_x2Fm_wh" BETWEEN {ENERGY_PRICE_MIN} AND {ENERGY_PRICE_MAX}
                  {time_filter}
            )
            SELECT
                epoch({bucket_expr})::BIGINT AS t,
                first(price_eur_mwh ORDER BY date_time_utc) AS o,
                max(price_eur_mwh) AS h,
                min(price_eur_mwh) AS l,
                last(price_eur_mwh ORDER BY date_time_utc) AS c,
                count(*)::DOUBLE AS v
            FROM raw
            GROUP BY t
            ORDER BY t DESC
        """

        if count_back > 0:
            sql += f" LIMIT {count_back}"

        try:
            rows = self.conn.execute(sql).fetchall()
        except Exception as e:
            logger.error("DuckDB query failed for %s: %s", symbol, e)
            raise

        bars: list[Bar] = []
        for row in reversed(rows):  # DESC query → reverse to ascending for chart
            o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
            # If flat candle (O=H=L=C), add tiny spread so chart renders candlestick body
            if abs(h - l) < 0.001:
                spread = max(abs(o) * 0.001, 0.01)
                h = o + spread
                l = o - spread
            bars.append(Bar(
                time=row[0],
                open=round(o, 2),
                high=round(h, 2),
                low=round(l, 2),
                close=round(c, 2),
                volume=row[5],
            ))
        return bars

    def close(self) -> None:
        """Close DuckDB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
