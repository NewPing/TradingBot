"""Property-based tests for BucketLedger arithmetic and money conservation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from atlas.core.money import Money
from atlas.core.types import BucketId, Fill, Quantity, Side, Symbol
from atlas.portfolio.ledger import BucketLedger


@settings(max_examples=50)
@given(
    deposit_amount=st.decimals(
        min_value=Decimal("1000.00"), max_value=Decimal("1000000.00"), places=2
    ),
    trade_pct=st.decimals(min_value=Decimal("0.05"), max_value=Decimal("0.50"), places=2),
    buy_price=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("500.00"), places=2),
    sell_price=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("500.00"), places=2),
)
def test_ledger_equity_conservation_property(
    deposit_amount: Decimal,
    trade_pct: Decimal,
    buy_price: Decimal,
    sell_price: Decimal,
) -> None:
    ledger = BucketLedger(currency="USD")
    dep = Money(deposit_amount, "USD")
    ledger.deposit(dep)

    # Initial conservation
    assert ledger.total_cash() == dep
    assert ledger.total_equity({}) == dep

    # Buy in CORE bucket
    core_cash = ledger.accounts[BucketId.CORE].cash
    target_spend = core_cash * trade_pct
    qty = int(target_spend.amount // buy_price)

    if qty > 0:
        fill = Fill(
            order_id="ord-prop-buy",
            ts=datetime(2026, 1, 1, tzinfo=UTC),
            qty=Quantity(qty),
            price=buy_price,
            commission=Money.zero("USD"),
            fees=Money.zero("USD"),
            slippage_est=Money.zero("USD"),
            venue="MOCK",
        )
        ledger.execute_fill(fill, BucketId.CORE, Side.BUY, Symbol("TEST"))

        # Valuation at buy_price should perfectly match initial deposit
        eq_at_entry = ledger.total_equity({Symbol("TEST"): buy_price})
        assert eq_at_entry == dep

        # Sell half
        sell_qty = qty // 2
        if sell_qty > 0:
            sell_fill = Fill(
                order_id="ord-prop-sell",
                ts=datetime(2026, 1, 2, tzinfo=UTC),
                qty=Quantity(sell_qty),
                price=sell_price,
                commission=Money.zero("USD"),
                fees=Money.zero("USD"),
                slippage_est=Money.zero("USD"),
                venue="MOCK",
            )
            ledger.execute_fill(sell_fill, BucketId.CORE, Side.SELL, Symbol("TEST"))

            # Total equity = cash + remaining stock market value
            cur_eq = ledger.total_equity({Symbol("TEST"): sell_price})
            expected_pnl = Money(
                (sell_price - buy_price) * sell_qty + (sell_price - buy_price) * (qty - sell_qty),
                "USD",
            )
            assert cur_eq == dep + expected_pnl
