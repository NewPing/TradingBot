"""Unit and property-based tests for German Tax Accounting Engine and FIFO Lot Manager (Phase 9)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from atlas.accounting.ecb import ECBRateProvider
from atlas.accounting.tax import (
    FIFOLotManager,
    GermanTaxEngine,
)
from atlas.core.types import Side, Symbol


def test_ecb_rate_provider_defaults_and_conversions() -> None:
    provider = ECBRateProvider()
    d = date(2026, 8, 24)
    # Default rate is 1.0850 USD per EUR
    rate = provider.get_rate(d, "EUR", "USD")
    assert rate == Decimal("1.085000")

    # Base == target should return 1.0
    assert provider.get_rate(d, "EUR", "EUR") == Decimal("1.000000")
    assert provider.get_rate(d, "USD", "USD") == Decimal("1.000000")

    # 108.50 USD converted to EUR should be 100.00 EUR
    eur_amount = provider.convert_usd_to_eur(Decimal("108.50"), d)
    assert round(eur_amount, 2) == Decimal("100.00")

    # 100.00 EUR converted to USD should be 108.50 USD
    usd_amount = provider.convert_eur_to_usd(Decimal("100.00"), d)
    assert round(usd_amount, 2) == Decimal("108.50")


def test_fifo_lot_manager_buy_and_multi_sell() -> None:
    provider = ECBRateProvider()
    manager = FIFOLotManager(ecb_provider=provider)

    t1 = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    t2 = datetime(2026, 2, 10, 15, 0, tzinfo=UTC)
    t3 = datetime(2026, 3, 5, 16, 0, tzinfo=UTC)

    # Buy 100 shares of AAPL @ $200
    lot1 = manager.process_buy(
        symbol=Symbol("AAPL"),
        qty=100,
        price=Decimal("200.00"),
        ts=t1,
    )
    assert lot1.quantity_remaining == 100
    assert lot1.status == "OPEN"

    # Buy 50 shares of AAPL @ $220
    lot2 = manager.process_buy(
        symbol=Symbol("AAPL"),
        qty=50,
        price=Decimal("220.00"),
        ts=t2,
    )
    assert lot2.quantity_remaining == 50

    # Sell 120 shares of AAPL @ $250 -> Consumes 100 from lot1 and 20 from lot2
    allocs = manager.process_sell(
        symbol=Symbol("AAPL"),
        qty=120,
        price=Decimal("250.00"),
        ts=t3,
    )

    assert len(allocs) == 2
    assert allocs[0][0].id == lot1.id
    assert allocs[0][1] == 100  # 100 shares from lot1
    assert allocs[0][0].status == "CLOSED"
    assert allocs[0][0].quantity_remaining == 0

    assert allocs[1][0].id == lot2.id
    assert allocs[1][1] == 20  # 20 shares from lot2
    assert allocs[1][0].status == "PARTIAL"
    assert allocs[1][0].quantity_remaining == 30


def test_german_tax_engine_kest_soli_and_loss_pots() -> None:
    engine = GermanTaxEngine(sparerpauschbetrag=Decimal("1000.00"), church_tax_rate=Decimal("0.0"))
    t1 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 20, 15, 0, tzinfo=UTC)

    # Buy AAPL stock (AKTIEN)
    engine.record_trade(
        symbol=Symbol("AAPL"),
        side=Side.BUY,
        qty=100,
        price=Decimal("108.50"),  # = 100.00 EUR per share at 1.0850 rate
        ts=t1,
        asset_category="AKTIEN",
    )

    # Sell AAPL stock @ $162.75 (= 150.00 EUR per share) -> Gain +€5,000
    events = engine.record_trade(
        symbol=Symbol("AAPL"),
        side=Side.SELL,
        qty=100,
        price=Decimal("162.75"),
        ts=t2,
        asset_category="AKTIEN",
    )

    assert len(events) == 1
    ev = events[0]
    assert ev.gain_loss_eur == Decimal("5000.00")
    assert ev.is_gain is True

    # Generate annual tax report
    report = engine.generate_annual_tax_report(2026)
    assert report.total_realized_gains_eur == Decimal("5000.00")
    assert report.sparerpauschbetrag_used_eur == Decimal("1000.00")
    assert report.sparerpauschbetrag_remaining_eur == Decimal("0.00")
    # Taxable income = 5000 - 1000 = 4000 EUR
    assert report.net_taxable_income_eur == Decimal("4000.00")

    # KESt (25% of 4000) = 1000 EUR
    assert report.total_kest_eur == Decimal("1000.00")
    # Soli (5.5% of KESt = 55 EUR)
    assert report.total_soli_eur == Decimal("55.00")
    # Total tax = 1055.00 EUR
    assert report.total_tax_liability_eur == Decimal("1055.00")


def test_aktien_loss_pot_cannot_offset_other_gains() -> None:
    engine = GermanTaxEngine(sparerpauschbetrag=Decimal("0.00"))
    t1 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 20, 15, 0, tzinfo=UTC)

    # Buy SPY ETF (SONSTIGE)
    engine.record_trade(
        symbol=Symbol("SPY"),
        side=Side.BUY,
        qty=10,
        price=Decimal("108.50"),
        ts=t1,
        asset_category="SONSTIGE",
    )
    # Buy TSLA stock (AKTIEN)
    engine.record_trade(
        symbol=Symbol("TSLA"),
        side=Side.BUY,
        qty=50,
        price=Decimal("217.00"),
        ts=t1,
        asset_category="AKTIEN",
    )

    # Sell SPY ETF at profit (+€1,000 gain)
    engine.record_trade(
        symbol=Symbol("SPY"),
        side=Side.SELL,
        qty=10,
        price=Decimal("217.00"),
        ts=t2,
        asset_category="SONSTIGE",
    )

    # Sell TSLA stock at loss (-€2,000 loss)
    engine.record_trade(
        symbol=Symbol("TSLA"),
        side=Side.SELL,
        qty=50,
        price=Decimal("108.50"),
        ts=t2,
        asset_category="AKTIEN",
    )

    report = engine.generate_annual_tax_report(2026)
    # Under German § 20 Abs. 6 Satz 4 EStG:
    # Stock losses CANNOT offset ETF gains!
    # Therefore, Sonstige gain of €1,000 remains taxable, while Aktien loss of €5,000 carries forward.
    assert report.sonstige_gains_eur == Decimal("1000.00")
    assert report.aktien_loss_carryforward_eur > Decimal("0.00")
    assert report.net_taxable_income_eur == Decimal("1000.00")
    assert report.total_kest_eur == Decimal("250.00")


@given(
    qty=st.integers(min_value=1, max_value=500),
    buy_px=st.decimals(min_value=Decimal("10.0"), max_value=Decimal("500.0"), places=2),
    sell_px=st.decimals(min_value=Decimal("10.0"), max_value=Decimal("500.0"), places=2),
)
def test_property_tax_conservation(qty: int, buy_px: Decimal, sell_px: Decimal) -> None:
    engine = GermanTaxEngine(sparerpauschbetrag=Decimal("1000.00"))
    t1 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)

    engine.record_trade(
        symbol=Symbol("TEST"),
        side=Side.BUY,
        qty=qty,
        price=buy_px,
        ts=t1,
    )
    events = engine.record_trade(
        symbol=Symbol("TEST"),
        side=Side.SELL,
        qty=qty,
        price=sell_px,
        ts=t2,
    )

    assert len(events) == 1
    ev = events[0]
    assert ev.quantity == qty
    assert ev.total_tax_eur >= Decimal("0.00")
    if ev.gain_loss_eur <= Decimal("0.00"):
        assert ev.total_tax_eur == Decimal("0.00")
