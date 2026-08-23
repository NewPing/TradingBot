"""Unit tests for HardLimitsValidator and risk checks."""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal

from atlas.core.money import Money
from atlas.core.types import BucketId, Order, OrderType, Quantity, Side, Symbol, TimeInForce
from atlas.portfolio.ledger import BucketLedger
from atlas.risk.limits import HardLimitsValidator


def make_test_order(
    symbol: str = "AAPL",
    bucket: BucketId = BucketId.CORE,
    side: Side = Side.BUY,
    qty: int = 10,
    created_ts: datetime | None = None,
) -> Order:
    ts = created_ts or datetime(2026, 1, 15, 14, 0, tzinfo=UTC)
    return Order(
        id="test-ord",
        run_id="run-test",
        strategy_version_id="strat-v1",
        bucket=bucket,
        symbol=Symbol(symbol),
        side=side,
        qty=Quantity(qty),
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=ts,
    )


def test_hard_limits_pass_standard_order() -> None:
    validator = HardLimitsValidator()
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    order = make_test_order(qty=10)
    prices = {Symbol("AAPL"): Decimal("150.00")}

    results = validator.validate_order(order, ledger, prices)
    assert all(r.passed for r in results)


def test_single_symbol_limit_exceeded() -> None:
    validator = HardLimitsValidator(max_single_symbol_pct=Decimal("0.10"))
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    # Buy 100 shares @ $150 = $15,000 (15% of $100,000 total equity > 10% limit)
    order = make_test_order(qty=100)
    prices = {Symbol("AAPL"): Decimal("150.00")}

    results = validator.validate_order(order, ledger, prices)
    failed = [r for r in results if not r.passed]
    assert len(failed) > 0
    assert any(f.rule_name == "SINGLE_SYMBOL_LIMIT" for f in failed)


def test_sector_exposure_limit_exceeded() -> None:
    validator = HardLimitsValidator(max_sector_pct=Decimal("0.30"))
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    order = make_test_order(qty=250)  # 250 * $150 = $37,500 (37.5% > 30%)
    prices = {Symbol("AAPL"): Decimal("150.00")}
    sectors = {Symbol("AAPL"): "Technology"}

    results = validator.validate_order(order, ledger, prices, symbol_sectors=sectors)
    failed = [r for r in results if not r.passed]
    assert any(f.rule_name == "SECTOR_EXPOSURE_LIMIT" for f in failed)


def test_adv_limit_exceeded() -> None:
    validator = HardLimitsValidator(max_adv_pct=Decimal("0.01"))
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    order = make_test_order(qty=50)  # 50 * $100 = $5,000
    prices = {Symbol("AAPL"): Decimal("100.00")}
    advs = {Symbol("AAPL"): Decimal("100000.00")}  # 1% of $100k = $1,000 max

    results = validator.validate_order(order, ledger, prices, symbol_adv=advs)
    failed = [r for r in results if not r.passed]
    assert any(f.rule_name == "ADV_LIMIT" for f in failed)


def test_session_cutoff_rule() -> None:
    validator = HardLimitsValidator(session_cutoff_minutes=10)
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    # Order created at 15:55 ET (20:55 UTC, within 10m of 16:00 ET close)
    ts = datetime(2026, 1, 15, 20, 55, tzinfo=UTC)
    order = make_test_order(created_ts=ts)
    prices = {Symbol("AAPL"): Decimal("100.00")}

    results = validator.validate_order(order, ledger, prices, market_close_time=time(16, 0))
    failed = [r for r in results if not r.passed]
    assert any(f.rule_name == "SESSION_CUTOFF" for f in failed)


def test_data_health_critical_rule() -> None:
    validator = HardLimitsValidator()
    ledger = BucketLedger()
    ledger.deposit(Money(Decimal("100000.00"), "USD"))

    order = make_test_order(symbol="BADSYM")
    prices = {Symbol("BADSYM"): Decimal("100.00")}
    critical_symbols = {Symbol("BADSYM")}

    results = validator.validate_order(
        order, ledger, prices, critical_data_symbols=critical_symbols
    )
    failed = [r for r in results if not r.passed]
    assert any(f.rule_name == "DATA_HEALTH_CRITICAL" for f in failed)
