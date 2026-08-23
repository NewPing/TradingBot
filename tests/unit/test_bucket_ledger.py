"""Unit tests for BucketLedger and isolated sub-account bookkeeping."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from atlas.core.errors import InsufficientCashError
from atlas.core.money import Money
from atlas.core.types import BucketId, Fill, Quantity, Side, Symbol
from atlas.portfolio.ledger import BucketLedger


def test_bucket_ledger_initialization_and_deposit() -> None:
    ledger = BucketLedger(currency="USD")
    assert ledger.total_cash() == Money.zero("USD")

    # Deposit $100,000 across buckets
    deposit_amt = Money(Decimal("100000.00"), "USD")
    ledger.deposit(deposit_amt)

    # Check target allocation split
    assert ledger.accounts[BucketId.CORE].cash == Money(Decimal("50000.00"), "USD")
    assert ledger.accounts[BucketId.SWING].cash == Money(Decimal("30000.00"), "USD")
    assert ledger.accounts[BucketId.MOONSHOT].cash == Money(Decimal("15000.00"), "USD")
    assert ledger.accounts[BucketId.CASH].cash == Money(Decimal("5000.00"), "USD")
    assert ledger.total_cash() == deposit_amt


def test_bucket_ledger_no_cross_borrowing() -> None:
    ledger = BucketLedger(currency="USD")
    ledger.deposit(Money(Decimal("10000.00"), "USD"))

    # SWING has $3,000 cash. Try to buy $4,000 worth of stock in SWING
    fill = Fill(
        order_id="ord-1",
        ts=datetime.now(UTC),
        qty=Quantity(40),
        price=Decimal("100.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="MOCK",
    )

    with pytest.raises(InsufficientCashError, match="strictly no inter-bucket borrowing"):
        ledger.execute_fill(fill, BucketId.SWING, Side.BUY, Symbol("AAPL"))


def test_bucket_ledger_buy_and_sell_lifecycle() -> None:
    ledger = BucketLedger(currency="USD")
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    # 1. Buy 100 AAPL @ $150.00 in CORE (Cost: $15,000 + $5 comm)
    buy_fill = Fill(
        order_id="ord-buy-1",
        ts=datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
        qty=Quantity(100),
        price=Decimal("150.00"),
        commission=Money(Decimal("5.00"), "USD"),
        fees=Money(Decimal("0.50"), "USD"),
        slippage_est=Money.zero("USD"),
        venue="MOCK",
    )
    pos = ledger.execute_fill(buy_fill, BucketId.CORE, Side.BUY, Symbol("AAPL"))
    assert pos is not None
    assert pos.qty == 100
    assert pos.avg_price == Decimal("150.00")
    assert ledger.accounts[BucketId.CORE].cash == Money(Decimal("34994.50"), "USD")

    # 2. Buy another 50 AAPL @ $165.00 in CORE
    buy_fill_2 = Fill(
        order_id="ord-buy-2",
        ts=datetime(2026, 1, 16, 14, 0, tzinfo=UTC),
        qty=Quantity(50),
        price=Decimal("165.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="MOCK",
    )
    pos2 = ledger.execute_fill(buy_fill_2, BucketId.CORE, Side.BUY, Symbol("AAPL"))
    assert pos2 is not None
    assert pos2.qty == 150
    # Avg price: (100*150 + 50*165) / 150 = (15000 + 8250)/150 = 23250/150 = 155.00
    assert pos2.avg_price == Decimal("155.00")

    # 3. Sell 50 AAPL @ $175.00 in CORE
    sell_fill = Fill(
        order_id="ord-sell-1",
        ts=datetime(2026, 1, 20, 14, 0, tzinfo=UTC),
        qty=Quantity(50),
        price=Decimal("175.00"),
        commission=Money(Decimal("2.00"), "USD"),
        fees=Money(Decimal("0.20"), "USD"),
        slippage_est=Money.zero("USD"),
        venue="MOCK",
    )
    pos3 = ledger.execute_fill(sell_fill, BucketId.CORE, Side.SELL, Symbol("AAPL"))
    assert pos3 is not None
    assert pos3.qty == 100
    # Realized P&L on 50 shares: 50 * (175 - 155) - 2.20 = 1000 - 2.20 = 997.80
    assert ledger.accounts[BucketId.CORE].realized_pnl == Money(Decimal("997.80"), "USD")

    # 4. Sell remaining 100 AAPL @ $180.00
    sell_fill_2 = Fill(
        order_id="ord-sell-2",
        ts=datetime(2026, 1, 22, 14, 0, tzinfo=UTC),
        qty=Quantity(100),
        price=Decimal("180.00"),
        commission=Money.zero("USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="MOCK",
    )
    pos4 = ledger.execute_fill(sell_fill_2, BucketId.CORE, Side.SELL, Symbol("AAPL"))
    assert pos4 is None
    assert Symbol("AAPL") not in ledger.accounts[BucketId.CORE].positions


def test_bucket_ledger_serialization_roundtrip() -> None:
    ledger = BucketLedger(currency="USD")
    ledger.deposit(Money(Decimal("50000.00"), "USD"))

    fill = Fill(
        order_id="ord-1",
        ts=datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
        qty=Quantity(20),
        price=Decimal("200.00"),
        commission=Money(Decimal("1.00"), "USD"),
        fees=Money.zero("USD"),
        slippage_est=Money.zero("USD"),
        venue="MOCK",
    )
    ledger.execute_fill(fill, BucketId.CORE, Side.BUY, Symbol("MSFT"), stop_px=Decimal("190.00"))

    # Serialize to dict and restore
    data = ledger.to_dict()
    restored = BucketLedger.from_dict(data)

    assert restored.currency == ledger.currency
    assert restored.total_cash() == ledger.total_cash()
    assert len(restored.all_positions()) == 1
    p = restored.accounts[BucketId.CORE].positions[Symbol("MSFT")]
    assert p.qty == 20
    assert p.avg_price == Decimal("200.00")
    assert p.stop_px == Decimal("190.00")
