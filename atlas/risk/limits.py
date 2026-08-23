"""Hard risk limits and order rejection rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from atlas.core.money import Money
from atlas.core.types import BucketId, Order, Side, Symbol
from atlas.portfolio.buckets import DEFAULT_BUCKET_CONFIGS, BucketConfig
from atlas.portfolio.ledger import BucketLedger


@dataclass(frozen=True, slots=True)
class RiskCheckResult:
    """Outcome of evaluating an order against risk rules."""

    passed: bool
    rule_name: str
    reason: str = ""


class HardLimitsValidator:
    """Evaluates proposed orders against Master Plan §6.3 hard limits."""

    def __init__(
        self,
        max_gross_exposure_pct: Decimal = Decimal("1.00"),  # 100%
        max_single_symbol_pct: Decimal = Decimal("0.10"),  # 10% across all buckets
        max_sector_pct: Decimal = Decimal("0.30"),  # 30% of total equity
        max_correlation: float = 0.85,  # 60d correlation guard
        max_adv_pct: Decimal = Decimal("0.01"),  # 1% of 20d ADV
        max_daily_orders_per_bucket: int = 20,
        session_cutoff_minutes: int = 10,
        bucket_configs: dict[BucketId, BucketConfig] | None = None,
    ) -> None:
        self.max_gross_exposure_pct = max_gross_exposure_pct
        self.max_single_symbol_pct = max_single_symbol_pct
        self.max_sector_pct = max_sector_pct
        self.max_correlation = max_correlation
        self.max_adv_pct = max_adv_pct
        self.max_daily_orders_per_bucket = max_daily_orders_per_bucket
        self.session_cutoff_minutes = session_cutoff_minutes
        self.bucket_configs = bucket_configs or DEFAULT_BUCKET_CONFIGS

    def validate_order(
        self,
        order: Order,
        ledger: BucketLedger,
        current_prices: dict[Symbol, Decimal],
        symbol_sectors: dict[Symbol, str] | None = None,
        symbol_adv: dict[Symbol, Decimal] | None = None,
        order_counts_today: dict[BucketId, int] | None = None,
        symbol_correlations: dict[tuple[Symbol, Symbol], float] | None = None,
        critical_data_symbols: set[Symbol] | None = None,
        market_close_time: time = time(16, 0),  # 16:00 ET / close
        is_simulated: bool = False,
        skip_session_cutoff: bool = False,
    ) -> list[RiskCheckResult]:
        """Validate an order against all §6.3 hard limits with long and short awareness."""
        results: list[RiskCheckResult] = []
        sectors = symbol_sectors or {}
        advs = symbol_adv or {}
        counts = order_counts_today or {}
        correlations = symbol_correlations or {}
        critical_symbols = critical_data_symbols or set()

        existing_pos = (
            ledger.accounts[order.bucket].positions.get(order.symbol)
            if order.bucket in ledger.accounts
            else None
        )
        if existing_pos is None:
            for b_acc in ledger.accounts.values():
                if order.symbol in b_acc.positions:
                    existing_pos = b_acc.positions[order.symbol]
                    break

        # Pure risk-reducing exits are always allowed
        if (
            order.side == Side.SELL
            and existing_pos is not None
            and existing_pos.qty > 0
            and order.qty <= existing_pos.qty
        ):
            return [RiskCheckResult(passed=True, rule_name="SELL_DECREASES_RISK")]

        if (
            order.side == Side.BUY
            and existing_pos is not None
            and existing_pos.qty < 0
            and order.qty <= abs(existing_pos.qty)
        ):
            return [RiskCheckResult(passed=True, rule_name="BUY_COVERS_SHORT_DECREASES_RISK")]

        # If selling to open short, verify bucket constraint
        if (
            order.side == Side.SELL
            and (existing_pos is None or existing_pos.qty <= 0)
            and order.bucket != BucketId.SWING
        ):
            return [
                RiskCheckResult(
                    passed=False,
                    rule_name="SHORT_BUCKET_RESTRICTION",
                    reason=f"Shorting is only allowed in SWING bucket, got {order.bucket}",
                )
            ]

        price = current_prices.get(order.symbol, order.limit_px or Decimal("0"))
        if price <= Decimal("0"):
            return [
                RiskCheckResult(
                    passed=False,
                    rule_name="PRICE_VALIDATION",
                    reason=f"No valid non-zero price for {order.symbol}",
                )
            ]

        order_notional = Money(price * Decimal(order.qty), ledger.currency)
        total_eq = ledger.total_equity(current_prices)

        if total_eq.amount <= Decimal("0"):
            return [
                RiskCheckResult(
                    passed=False,
                    rule_name="ZERO_EQUITY",
                    reason="Total equity is non-positive",
                )
            ]

        # 1. Critical Data Health check
        if order.symbol in critical_symbols:
            results.append(
                RiskCheckResult(
                    passed=False,
                    rule_name="DATA_HEALTH_CRITICAL",
                    reason=f"Symbol {order.symbol} has unresolved CRITICAL data health issue",
                )
            )

        # 2. Daily order count per bucket
        bucket_orders = counts.get(order.bucket, 0)
        if bucket_orders >= self.max_daily_orders_per_bucket:
            results.append(
                RiskCheckResult(
                    passed=False,
                    rule_name="ORDER_RATE_LIMIT",
                    reason=(
                        f"Bucket {order.bucket} reached daily order limit "
                        f"({bucket_orders}/{self.max_daily_orders_per_bucket})"
                    ),
                )
            )

        # 3. Session Cutoff Limit (no new entries in last 10 min of market trading session before close)
        if not is_simulated and not skip_session_cutoff:
            order_dt = (
                order.created_ts
                if order.created_ts.tzinfo is not None
                else order.created_ts.replace(tzinfo=UTC)
            )
            ny_tz = ZoneInfo("America/New_York")
            order_time_ny = order_dt.astimezone(ny_tz).time()
            close_mins = market_close_time.hour * 60 + market_close_time.minute
            order_mins = order_time_ny.hour * 60 + order_time_ny.minute
            if 0 < (close_mins - order_mins) <= self.session_cutoff_minutes:
                results.append(
                    RiskCheckResult(
                        passed=False,
                        rule_name="SESSION_CUTOFF",
                        reason=(
                            f"Order at {order_time_ny} ET is within {self.session_cutoff_minutes}m "
                            f"of market close ({market_close_time} ET)"
                        ),
                    )
                )

        # 4. ADV Limit (Order notional <= 1% of 20d ADV)
        adv = advs.get(order.symbol)
        if adv is not None and adv > Decimal("0"):
            max_allowed_notional = adv * self.max_adv_pct
            if order_notional.amount > max_allowed_notional:
                results.append(
                    RiskCheckResult(
                        passed=False,
                        rule_name="ADV_LIMIT",
                        reason=(
                            f"Order notional ${order_notional.amount:,.2f} exceeds "
                            f"{self.max_adv_pct * 100}% of 20d ADV (${max_allowed_notional:,.2f})"
                        ),
                    )
                )

        # Calculate post-trade position and notional for the target order's bucket
        bucket_acc = ledger.accounts.get(order.bucket)
        existing_sym_in_bucket = (
            order.symbol in bucket_acc.positions if bucket_acc is not None else False
        )
        current_qty = (
            bucket_acc.positions[order.symbol].qty
            if (bucket_acc is not None and existing_sym_in_bucket)
            else 0
        )
        order_delta = order.qty if order.side == Side.BUY else -order.qty
        net_post_qty = current_qty + order_delta
        post_bucket_notional = price * abs(net_post_qty)

        # 5. Bucket capacity and single position limits
        bucket_cfg = self.bucket_configs.get(order.bucket)
        if bucket_cfg and bucket_acc is not None:
            bucket_eq = bucket_acc.equity(current_prices)

            if not existing_sym_in_bucket and len(bucket_acc.positions) >= bucket_cfg.max_positions:
                results.append(
                    RiskCheckResult(
                        passed=False,
                        rule_name="BUCKET_MAX_POSITIONS",
                        reason=(
                            f"Bucket {order.bucket} at max position capacity "
                            f"({len(bucket_acc.positions)}/{bucket_cfg.max_positions})"
                        ),
                    )
                )

            if bucket_eq.amount > Decimal("0"):
                bucket_pct = post_bucket_notional / bucket_eq.amount
                if bucket_pct > bucket_cfg.max_single_position_pct:
                    results.append(
                        RiskCheckResult(
                            passed=False,
                            rule_name="BUCKET_CONCENTRATION_LIMIT",
                            reason=(
                                f"Post-trade position {bucket_pct:.1%} of bucket equity "
                                f"exceeds limit {bucket_cfg.max_single_position_pct:.1%}"
                            ),
                        )
                    )

            for existing_sym in bucket_acc.positions:
                if existing_sym != order.symbol:
                    corr = correlations.get(
                        (order.symbol, existing_sym),
                        correlations.get((existing_sym, order.symbol), 0.0),
                    )
                    if corr > self.max_correlation:
                        results.append(
                            RiskCheckResult(
                                passed=False,
                                rule_name="CORRELATION_GUARD",
                                reason=(
                                    f"Correlation {corr:.2f} with {existing_sym} in bucket "
                                    f"{order.bucket} exceeds max {self.max_correlation:.2f}"
                                ),
                            )
                        )

        # 6. Single Symbol Limit across all buckets (<= 10% of total equity)
        current_tot_sym_qty = 0
        for acc in ledger.accounts.values():
            if order.symbol in acc.positions:
                current_tot_sym_qty += acc.positions[order.symbol].qty
        post_tot_sym_qty = current_tot_sym_qty + (
            order.qty if order.side == Side.BUY else -order.qty
        )
        post_sym_total = price * abs(post_tot_sym_qty)
        sym_total_pct = post_sym_total / total_eq.amount
        if sym_total_pct > self.max_single_symbol_pct:
            results.append(
                RiskCheckResult(
                    passed=False,
                    rule_name="SINGLE_SYMBOL_LIMIT",
                    reason=(
                        f"Post-trade total {order.symbol} exposure {sym_total_pct:.1%} "
                        f"exceeds max {self.max_single_symbol_pct:.1%} of total equity"
                    ),
                )
            )

        # 7. Sector Exposure Limit (<= 30% of total equity)
        target_sector = sectors.get(order.symbol)
        if target_sector:
            post_sector_notional = Decimal("0")
            for acc in ledger.accounts.values():
                for p_sym, p_pos in acc.positions.items():
                    if sectors.get(p_sym) == target_sector:
                        p_px = current_prices.get(p_sym, p_pos.avg_price)
                        if p_sym == order.symbol and acc.bucket_id == order.bucket:
                            continue  # Handled below via post_bucket_notional
                        post_sector_notional += p_px * abs(p_pos.qty)
            post_sector_notional += post_bucket_notional
            sector_pct = post_sector_notional / total_eq.amount
            if sector_pct > self.max_sector_pct:
                results.append(
                    RiskCheckResult(
                        passed=False,
                        rule_name="SECTOR_EXPOSURE_LIMIT",
                        reason=(
                            f"Post-trade sector '{target_sector}' exposure {sector_pct:.1%} "
                            f"exceeds max {self.max_sector_pct:.1%} of total equity"
                        ),
                    )
                )

        # 8. Gross Exposure Cap (<= 100% of total equity, |long| + |short|)
        current_gross_mv = Decimal("0")
        for acc in ledger.accounts.values():
            for p_sym, p_pos in acc.positions.items():
                p_px = current_prices.get(p_sym, p_pos.avg_price)
                if p_sym == order.symbol and order.bucket == acc.bucket_id:
                    continue  # Replaced by post_bucket_notional
                current_gross_mv += p_px * abs(p_pos.qty)
        post_gross_mv = current_gross_mv + post_bucket_notional
        gross_pct = post_gross_mv / total_eq.amount
        if gross_pct > self.max_gross_exposure_pct:
            results.append(
                RiskCheckResult(
                    passed=False,
                    rule_name="GROSS_EXPOSURE_LIMIT",
                    reason=(
                        f"Post-trade gross exposure {gross_pct:.1%} exceeds "
                        f"max {self.max_gross_exposure_pct:.1%} of equity"
                    ),
                )
            )

        if not results:
            results.append(RiskCheckResult(passed=True, rule_name="ALL_LIMITS_PASSED"))

        return results
