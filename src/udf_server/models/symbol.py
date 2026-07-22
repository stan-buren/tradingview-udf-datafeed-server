"""UDF protocol models — exactly as TradingView spec defines them."""

from __future__ import annotations

from pydantic import BaseModel


# ─── UDF Configuration ───────────────────────────────────────────


class Exchange(BaseModel):
    value: str
    name: str
    desc: str


class SymbolType(BaseModel):
    name: str
    value: str


class DatafeedConfiguration(BaseModel):
    supported_resolutions: list[str]
    supports_search: bool = True
    supports_group_request: bool = False
    supports_marks: bool = False
    supports_timescale_marks: bool = False
    exchanges: list[Exchange]
    symbols_types: list[SymbolType]
    intraday_multipliers: list[str] | None = None


# ─── Symbol Search ───────────────────────────────────────────────


class SearchResultItem(BaseModel):
    symbol: str
    full_name: str
    description: str
    exchange: str
    ticker: str
    type: str


# ─── Library Symbol Info ─────────────────────────────────────────


class LibrarySymbolInfo(BaseModel):
    """Full symbol metadata returned by /symbols."""

    name: str
    ticker: str
    description: str
    type: str = "crypto"
    session: str = "24x7"
    timezone: str = "Etc/UTC"
    exchange: str = "Binance"
    listed_exchange: str = "Binance"

    minmov: int = 1
    pricescale: int = 100
    has_intraday: bool = True
    has_daily: bool = True
    has_weekly_and_monthly: bool = True

    supported_resolutions: list[str] = ["1", "5", "15", "60", "240", "1D", "1W", "1M"]
    intraday_multipliers: list[str] = ["1", "5", "15", "60", "240"]
    daily_multipliers: list[str] = ["1D"]

    volume_precision: int = 8
    data_status: str = "streaming"
    format: str = "price"

    visible_plots_set: str = "ohlcv"
