"""Tests for Bar and HistoryResponse models."""

from src.udf_server.models.bar import Bar, HistoryResponse


class TestBar:
    def test_create(self) -> None:
        b = Bar(time=100, open=1.0, high=2.0, low=0.5, close=1.5, volume=1000.0)
        assert b.time == 100
        assert b.close == 1.5

    def test_slots(self) -> None:
        """Bar uses __slots__ — no __dict__."""
        b = Bar(time=1, open=1.0, high=1.0, low=1.0, close=1.0, volume=0.0)
        assert not hasattr(b, "__dict__")


class TestHistoryResponse:
    def test_from_bars(self) -> None:
        bars = [
            Bar(time=100, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0),
            Bar(time=200, open=1.5, high=2.5, low=1.0, close=2.0, volume=200.0),
        ]
        resp = HistoryResponse.from_bars(bars)
        assert resp.s == "ok"
        assert resp.t == [100, 200]
        assert resp.c == [1.5, 2.0]
        assert resp.o == [1.0, 1.5]
        assert resp.h == [2.0, 2.5]
        assert resp.l == [0.5, 1.0]
        assert resp.v == [100.0, 200.0]

    def test_no_data(self) -> None:
        resp = HistoryResponse.no_data(next_time=12345)
        assert resp.s == "no_data"
        assert resp.t == []
        assert resp.nextTime == 12345

    def test_error(self) -> None:
        resp = HistoryResponse.error("Something went wrong")
        assert resp.s == "error"
        assert resp.errmsg == "Something went wrong"
        assert resp.t == []

    def test_empty_bars(self) -> None:
        resp = HistoryResponse.from_bars([])
        assert resp.s == "ok"
        assert resp.t == []
        assert resp.c == []
