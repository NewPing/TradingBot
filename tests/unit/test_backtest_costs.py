"""Unit tests for transaction cost model costs.default_v1."""

from __future__ import annotations

from decimal import Decimal

from atlas.backtest.costs import DefaultCostModelV1
from atlas.core.money import Money
from atlas.core.types import Side


def test_spread_calculation() -> None:
    cost_model = DefaultCostModelV1()

    # Price $100, High ADV ($60M > $50M) -> half_spread = max(0.01, 100 * 0.0004 = 0.04) -> 0.04
    spread_high_adv = cost_model.calculate_half_spread(Decimal("100.00"), Decimal("60000000"))
    assert spread_high_adv == Decimal("0.04")

    # Price $10, High ADV -> max(0.01, 10 * 0.0004 = 0.004) -> 0.01 (min cap)
    spread_min_cap = cost_model.calculate_half_spread(Decimal("10.00"), Decimal("60000000"))
    assert spread_min_cap == Decimal("0.01")

    # Price $100, Low ADV ($10M < $50M) -> max(0.01, 100 * 0.0010 = 0.10) -> 0.10
    spread_low_adv = cost_model.calculate_half_spread(Decimal("100.00"), Decimal("10000000"))
    assert spread_low_adv == Decimal("0.10")


def test_regulatory_fees_only_on_sell() -> None:
    cost_model = DefaultCostModelV1()

    # BUY -> zero regulatory fees
    buy_fees = cost_model.calculate_regulatory_fees(Side.BUY, 1000, Decimal("50.00"))
    assert buy_fees == Money.zero("USD")

    # SELL -> SEC ($0.0000278 * 50,000 = $1.39) + FINRA ($0.000166 * 1000 = $0.166)
    sell_fees = cost_model.calculate_regulatory_fees(Side.SELL, 1000, Decimal("50.00"))
    expected_sec = Decimal("50000") * Decimal("0.0000278")
    expected_finra = Decimal("1000") * Decimal("0.000166")
    assert sell_fees == Money(expected_sec + expected_finra, "USD")


def test_finra_fee_cap() -> None:
    cost_model = DefaultCostModelV1()

    # Large order 1,000,000 shares -> FINRA fee uncapped would be $166 -> capped at $8.30
    sell_fees = cost_model.calculate_regulatory_fees(Side.SELL, 1000000, Decimal("10.00"))
    expected_sec = Decimal("10000000") * Decimal("0.0000278")
    assert sell_fees == Money(expected_sec + Decimal("8.30"), "USD")


def test_slippage_scaling() -> None:
    cost_model_k1 = DefaultCostModelV1(k=1.0)
    cost_model_k15 = DefaultCostModelV1(k=1.5)

    adv = Decimal("10000000")
    price = Decimal("100.00")
    qty = 1000

    slip1 = cost_model_k1.calculate_slippage(qty, price, adv, Decimal("0.02"))
    slip15 = cost_model_k15.calculate_slippage(qty, price, adv, Decimal("0.02"))

    assert slip15 > slip1
    assert abs(float(slip15 / slip1) - 1.5) < 1e-4


def test_evaluate_fill_buy_and_sell() -> None:
    cost_model = DefaultCostModelV1(broker_commission_type="alpaca")
    adv = Decimal("60000000")
    base_price = Decimal("100.00")
    qty = 100

    # BUY fill price must be higher than base_price
    buy_res = cost_model.evaluate_fill(Side.BUY, qty, base_price, adv)
    assert buy_res.fill_price > base_price
    assert buy_res.commission == Money.zero("USD")
    assert buy_res.regulatory_fees == Money.zero("USD")

    # SELL fill price must be lower than base_price
    sell_res = cost_model.evaluate_fill(Side.SELL, qty, base_price, adv)
    assert sell_res.fill_price < base_price
    assert sell_res.regulatory_fees.amount > Decimal("0")


def test_ibkr_commission_calculation() -> None:
    cost_model = DefaultCostModelV1(broker_commission_type="ibkr")

    # 100 shares @ $50 -> per-share $0.35, min $0.35 -> $0.35
    comm1 = cost_model.calculate_commission(100, Decimal("50.00"))
    assert comm1 == Money(Decimal("0.35"), "USD")

    # 1000 shares @ $50 -> per-share $3.50 -> $3.50
    comm2 = cost_model.calculate_commission(1000, Decimal("50.00"))
    assert comm2 == Money(Decimal("3.50"), "USD")

    # 10 shares @ $1 -> value $10 -> max 1% is $0.10 -> capped at $0.10
    comm3 = cost_model.calculate_commission(10, Decimal("1.00"))
    assert comm3 == Money(Decimal("0.10"), "USD")
