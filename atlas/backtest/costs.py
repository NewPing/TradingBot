"""Pessimistic transaction cost model (costs.default_v1) for backtesting and simulation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from atlas.core.money import Money
from atlas.core.types import Side


@dataclass(frozen=True, slots=True)
class CostResult:
    """Breakdown of transaction costs incurred for an executed order."""

    fill_price: Decimal
    commission: Money
    regulatory_fees: Money
    half_spread: Decimal
    slippage: Decimal
    total_cost_usd: Money


@dataclass(frozen=True, slots=True)
class DefaultCostModelV1:
    """Pessimistic cost model implementation per Section 7 of ATLAS specification.

    - Commission: Alpaca $0 default (or IBKR $0.0035/share, min $0.35, max 1%).
    - Regulatory fees: SEC fee ($0.0000278 * sell notional) + FINRA TAF ($0.000166/share, cap $8.30) on SELLS.
    - Half-spread: max($0.01, 0.0004 * price) for ADV > $50M, else 0.0010 * price.
    - Slippage: k * daily_vol * sqrt(order_notional / ADV) with k = 1.0 default.
    """

    k: float = 1.0
    broker_commission_type: str = "alpaca"  # 'alpaca' or 'ibkr'
    sec_fee_rate: Decimal = Decimal("0.0000278")
    finra_taf_rate: Decimal = Decimal("0.000166")
    finra_taf_cap: Decimal = Decimal("8.30")
    adv_high_threshold_usd: Decimal = Decimal("50000000")  # $50M
    default_daily_vol: Decimal = Decimal("0.02")  # 2% default if not available
    cash_yield_annual: Decimal = Decimal("0.04")  # 4% annual on idle cash
    borrow_rate_annual: Decimal = Decimal("0.03")  # 3% annual on short notional

    def calculate_commission(self, qty: int, price: Decimal) -> Money:
        """Calculate broker commission."""
        if qty <= 0:
            return Money.zero("USD")

        if self.broker_commission_type.lower() == "ibkr":
            # $0.0035/share, min $0.35, max 1% of trade value
            notional = Decimal(qty) * price
            per_share_comm = Decimal(qty) * Decimal("0.0035")
            comm = max(Decimal("0.35"), per_share_comm)
            max_comm = notional * Decimal("0.01")
            comm = min(comm, max_comm)
            return Money(comm, "USD")

        # Alpaca commission free
        return Money.zero("USD")

    def calculate_regulatory_fees(self, side: Side, qty: int, price: Decimal) -> Money:
        """Calculate SEC & FINRA regulatory fees (applies on SELL only)."""
        if side != Side.SELL or qty <= 0:
            return Money.zero("USD")

        notional = Decimal(qty) * price
        sec_fee = notional * self.sec_fee_rate
        finra_fee = min(Decimal(qty) * self.finra_taf_rate, self.finra_taf_cap)

        return Money(sec_fee + finra_fee, "USD")

    def calculate_half_spread(self, price: Decimal, adv_usd: Decimal) -> Decimal:
        """Calculate half-spread per share."""
        if adv_usd >= self.adv_high_threshold_usd:
            spread = max(Decimal("0.01"), price * Decimal("0.0004"))
        else:
            spread = max(Decimal("0.01"), price * Decimal("0.0010"))
        return spread

    def calculate_slippage(
        self,
        qty: int,
        price: Decimal,
        adv_usd: Decimal,
        daily_vol: Decimal | None = None,
    ) -> Decimal:
        """Calculate slippage per share using market-impact square-root law:

        slippage_pct = k * sigma_daily * sqrt(order_notional / ADV)
        slippage_usd_per_share = price * slippage_pct
        """
        if qty <= 0 or price <= Decimal("0"):
            return Decimal("0")

        vol = (
            daily_vol
            if (daily_vol is not None and daily_vol > Decimal("0"))
            else self.default_daily_vol
        )
        order_notional = Decimal(qty) * price

        adv = adv_usd if adv_usd > Decimal("0") else Decimal("10000000")
        impact_ratio = float(order_notional / adv)
        slippage_pct = Decimal(str(self.k)) * vol * Decimal(str(math.sqrt(max(0.0, impact_ratio))))

        return price * slippage_pct

    def evaluate_fill(
        self,
        side: Side,
        qty: int,
        base_price: Decimal,
        adv_usd: Decimal,
        daily_vol: Decimal | None = None,
    ) -> CostResult:
        """Calculate execution fill price including spread, slippage, and calculate all fees."""
        if qty <= 0:
            raise ValueError(f"Quantity must be positive: {qty}")
        if base_price <= Decimal("0"):
            raise ValueError(f"Base price must be positive: {base_price}")

        half_spread = self.calculate_half_spread(base_price, adv_usd)
        slippage = self.calculate_slippage(qty, base_price, adv_usd, daily_vol)

        if side == Side.BUY:
            fill_price = base_price + half_spread + slippage
        else:
            fill_price = max(Decimal("0.0001"), base_price - half_spread - slippage)

        commission = self.calculate_commission(qty, fill_price)
        regulatory_fees = self.calculate_regulatory_fees(side, qty, fill_price)

        total_price_impact = (half_spread + slippage) * Decimal(qty)
        total_cost_usd = Money(total_price_impact, "USD") + commission + regulatory_fees

        return CostResult(
            fill_price=fill_price,
            commission=commission,
            regulatory_fees=regulatory_fees,
            half_spread=half_spread,
            slippage=slippage,
            total_cost_usd=total_cost_usd,
        )
