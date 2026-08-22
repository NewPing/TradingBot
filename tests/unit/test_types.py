"""Unit tests for core domain types and invariants."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from atlas.core.money import Money
from atlas.core.types import (
    AccountState,
    Bar,
    BucketId,
    Fill,
    FundamentalSnapshot,
    NewsItem,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Signal,
    SignalLayer,
    Symbol,
    TimeInForce,
)


def test_bar_valid_creation() -> None:
    now_utc = datetime.now(UTC)
    bar = Bar(
        symbol=Symbol("AAPL"),
        ts=now_utc,
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("154.00"),
        volume=1000000,
    )
    assert bar.symbol == "AAPL"
    assert bar.close == Decimal("154.00")


def test_bar_rejects_naive_timestamp() -> None:
    naive_dt = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Bar(
            symbol=Symbol("AAPL"),
            ts=naive_dt,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
            volume=1000,
        )


def test_bar_rejects_invalid_high_low() -> None:
    now_utc = datetime.now(UTC)
    with pytest.raises(ValueError, match="cannot be less than low"):
        Bar(
            symbol=Symbol("AAPL"),
            ts=now_utc,
            open=Decimal("150.00"),
            high=Decimal("140.00"),
            low=Decimal("155.00"),
            close=Decimal("150.00"),
            volume=1000,
        )


def test_bar_rejects_open_outside_range() -> None:
    now_utc = datetime.now(UTC)
    with pytest.raises(ValueError, match="must be within"):
        Bar(
            symbol=Symbol("AAPL"),
            ts=now_utc,
            open=Decimal("160.00"),
            high=Decimal("155.00"),
            low=Decimal("140.00"),
            close=Decimal("150.00"),
            volume=1000,
        )


def test_bar_rejects_close_outside_range() -> None:
    now_utc = datetime.now(UTC)
    with pytest.raises(ValueError, match="must be within"):
        Bar(
            symbol=Symbol("AAPL"),
            ts=now_utc,
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("140.00"),
            close=Decimal("130.00"),
            volume=1000,
        )


def test_signal_bounds_validation() -> None:
    now_utc = datetime.now(UTC)

    # Valid signal
    sig = Signal(
        provider="l1.momentum",
        layer=SignalLayer.L1_TECHNICAL,
        symbol=Symbol("SPY"),
        ts=now_utc,
        score=0.75,
        confidence=0.9,
    )
    assert sig.score == 0.75

    # Out of bounds score
    with pytest.raises(ValueError, match="score must be within"):
        Signal(
            provider="l1.momentum",
            layer=SignalLayer.L1_TECHNICAL,
            symbol=Symbol("SPY"),
            ts=now_utc,
            score=1.5,
            confidence=0.5,
        )

    # Out of bounds confidence
    with pytest.raises(ValueError, match="confidence must be within"):
        Signal(
            provider="l1.momentum",
            layer=SignalLayer.L1_TECHNICAL,
            symbol=Symbol("SPY"),
            ts=now_utc,
            score=0.5,
            confidence=-0.1,
        )

    # Naive timestamp
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Signal(
            provider="l1.momentum",
            layer=SignalLayer.L1_TECHNICAL,
            symbol=Symbol("SPY"),
            ts=datetime(2026, 1, 1),
            score=0.5,
            confidence=0.5,
        )


def test_order_creation_and_validation() -> None:
    now_utc = datetime.now(UTC)
    order = Order(
        id="ord-001",
        run_id="run-001",
        strategy_version_id="strat-v1",
        bucket=BucketId.CORE,
        symbol=Symbol("QQQ"),
        side=Side.BUY,
        qty=50,
        type=OrderType.LIMIT,
        tif=TimeInForce.DAY,
        created_ts=now_utc,
        limit_px=Decimal("450.00"),
        status=OrderStatus.NEW,
    )
    assert order.qty == 50
    assert order.bucket == BucketId.CORE

    # Reject non-positive quantity
    with pytest.raises(ValueError, match="quantity must be positive"):
        Order(
            id="ord-002",
            run_id="run-001",
            strategy_version_id="strat-v1",
            bucket=BucketId.CORE,
            symbol=Symbol("QQQ"),
            side=Side.BUY,
            qty=0,
            type=OrderType.MARKET,
            tif=TimeInForce.DAY,
            created_ts=now_utc,
        )

    # Reject naive timestamp
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Order(
            id="ord-003",
            run_id="run-001",
            strategy_version_id="strat-v1",
            bucket=BucketId.CORE,
            symbol=Symbol("QQQ"),
            side=Side.BUY,
            qty=10,
            type=OrderType.MARKET,
            tif=TimeInForce.DAY,
            created_ts=datetime(2026, 1, 1),
        )


def test_fill_creation_and_validation() -> None:
    now_utc = datetime.now(UTC)
    fill = Fill(
        order_id="ord-001",
        ts=now_utc,
        qty=50,
        price=Decimal("449.50"),
        commission=Money.zero(),
        fees=Money("0.05"),
        slippage_est=Money("0.10"),
        venue="Alpaca",
    )
    assert fill.qty == 50
    assert fill.price == Decimal("449.50")

    # Reject non-positive qty
    with pytest.raises(ValueError, match="quantity must be positive"):
        Fill(
            order_id="ord-001",
            ts=now_utc,
            qty=0,
            price=Decimal("449.50"),
            commission=Money.zero(),
            fees=Money.zero(),
            slippage_est=Money.zero(),
            venue="Alpaca",
        )

    # Reject naive timestamp
    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Fill(
            order_id="ord-001",
            ts=datetime(2026, 1, 1),
            qty=10,
            price=Decimal("449.50"),
            commission=Money.zero(),
            fees=Money.zero(),
            slippage_est=Money.zero(),
            venue="Alpaca",
        )


def test_position_and_account_state() -> None:
    now_utc = datetime.now(UTC)
    pos = Position(
        symbol=Symbol("AAPL"),
        bucket=BucketId.CORE,
        qty=100,
        avg_price=Decimal("150.00"),
        opened_ts=now_utc,
        unrealized=Money("200.00"),
        realized=Money.zero(),
    )
    assert pos.symbol == "AAPL"
    assert pos.qty == 100

    with pytest.raises(ValueError, match="must be timezone-aware UTC"):
        Position(
            symbol=Symbol("AAPL"),
            bucket=BucketId.CORE,
            qty=100,
            avg_price=Decimal("150.00"),
            opened_ts=datetime(2026, 1, 1),
            unrealized=Money.zero(),
            realized=Money.zero(),
        )

    acc = AccountState(
        ts=now_utc,
        total_equity=Money("100000.00"),
        cash=Money("50000.00"),
        buying_power=Money("50000.00"),
        per_bucket_equity={BucketId.CORE: Money("50000.00")},
    )
    assert acc.total_equity == Money("100000.00")


def test_news_and_fundamental_records() -> None:
    now_utc = datetime.now(UTC)
    news = NewsItem(
        id="news-001",
        ts=now_utc,
        source="alpaca",
        symbols=(Symbol("AAPL"),),
        title="Apple Q3 Record",
        body="...",
        url="https://example.com",
    )
    assert news.symbols[0] == "AAPL"

    fund = FundamentalSnapshot(
        symbol=Symbol("AAPL"),
        report_date=now_utc,
        filing_date=now_utc,
        period="Q3-2026",
        metrics={"pe_ratio": 28.5},
    )
    assert fund.metrics["pe_ratio"] == 28.5
