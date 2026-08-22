"""Unit tests for data normalization and corporate action adjustments."""

from datetime import UTC, date, datetime
from decimal import Decimal

from atlas.core.types import Bar, Symbol
from atlas.data.normalize import (
    compute_adjusted_series,
    normalize_alpaca_bar,
    normalize_tiingo_bar,
    parse_date_to_utc_close,
)


def test_parse_date_to_utc_close() -> None:
    dt1 = parse_date_to_utc_close("2023-01-03")
    assert dt1.year == 2023 and dt1.month == 1 and dt1.day == 3
    assert dt1.hour == 21 and dt1.minute == 0
    assert dt1.tzinfo == UTC

    d2 = date(2024, 5, 1)
    dt2 = parse_date_to_utc_close(d2)
    assert dt2.tzinfo == UTC


def test_normalize_tiingo_bar() -> None:
    raw = {
        "date": "2023-01-03T00:00:00.000Z",
        "close": 125.07,
        "high": 130.90,
        "low": 124.17,
        "open": 130.28,
        "volume": 112117500,
        "adjClose": 124.30,
    }
    bar = normalize_tiingo_bar(raw, Symbol("AAPL"))
    assert bar.symbol == Symbol("AAPL")
    assert bar.open == Decimal("130.2800")
    assert bar.high == Decimal("130.9000")
    assert bar.low == Decimal("124.1700")
    assert bar.close == Decimal("125.0700")
    assert bar.volume == 112117500
    assert bar.source == "tiingo"
    assert bar.adj_factor > Decimal("0")


def test_normalize_alpaca_bar() -> None:
    raw = {
        "t": "2023-01-03T05:00:00Z",
        "o": 130.28,
        "h": 130.90,
        "l": 124.17,
        "c": 125.07,
        "v": 112117471,
        "vw": 125.7202,
    }
    bar = normalize_alpaca_bar(raw, Symbol("AAPL"))
    assert bar.symbol == Symbol("AAPL")
    assert bar.close == Decimal("125.0700")
    assert bar.vwap == Decimal("125.7202")
    assert bar.source == "alpaca"


def test_compute_adjusted_series_with_split() -> None:
    # 2 days of bars, 2-for-1 split on day 2
    b1 = Bar(
        symbol=Symbol("XYZ"),
        ts=datetime(2023, 1, 3, 21, 0, 0, tzinfo=UTC),
        open=Decimal("200.0"),
        high=Decimal("205.0"),
        low=Decimal("195.0"),
        close=Decimal("200.0"),
        volume=1000,
    )
    b2 = Bar(
        symbol=Symbol("XYZ"),
        ts=datetime(2023, 1, 4, 21, 0, 0, tzinfo=UTC),
        open=Decimal("100.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal("100.0"),
        volume=2000,
    )

    corporate_actions = [
        {
            "symbol": "XYZ",
            "ex_date": date(2023, 1, 4),
            "action_type": "SPLIT",
            "ratio": 2.0,
        }
    ]

    adjusted = compute_adjusted_series([b1, b2], corporate_actions)
    assert len(adjusted) == 2
    # Day 1 historical adjustment factor should be 0.5 (1.0 / 2.0)
    assert adjusted[0].adj_factor == Decimal("0.50000000")
    # Day 2 should have adj_factor 1.0
    assert adjusted[1].adj_factor == Decimal("1.00000000")
