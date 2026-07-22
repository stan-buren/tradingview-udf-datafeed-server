"""Bar and history response models — UDF columnar format."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Bar:
    """Single OHLCV candle. Timestamps in seconds."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class HistoryResponse:
    """Columnar format per UDF spec: {s, t[], c[], o[], h[], l[], v[]}.

    When s="ok", all arrays are present.
    When s="no_data", nextTime is set and arrays are empty.
    When s="error", errmsg is set.
    """

    s: str  # "ok" | "no_data" | "error"
    t: list[int] = field(default_factory=list)
    c: list[float] = field(default_factory=list)
    o: list[float] = field(default_factory=list)
    h: list[float] = field(default_factory=list)
    l: list[float] = field(default_factory=list)
    v: list[float] = field(default_factory=list)
    nextTime: int | None = None
    errmsg: str | None = None

    @classmethod
    def from_bars(cls, bars: list[Bar]) -> HistoryResponse:
        """Convert a list of Bar objects to UDF columnar response."""
        return cls(
            s="ok",
            t=[b.time for b in bars],
            c=[b.close for b in bars],
            o=[b.open for b in bars],
            h=[b.high for b in bars],
            l=[b.low for b in bars],
            v=[b.volume for b in bars],
        )

    @classmethod
    def no_data(cls, next_time: int | None = None) -> HistoryResponse:
        return cls(s="no_data", nextTime=next_time)

    @classmethod
    def error(cls, msg: str) -> HistoryResponse:
        return cls(s="error", errmsg=msg)
