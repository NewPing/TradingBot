"""Bucket ledger and isolated sub-account bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from atlas.core.errors import InsufficientCashError
from atlas.core.money import Money
from atlas.core.types import (
    AccountState,
    BucketId,
    Fill,
    Position,
    Quantity,
    Side,
    Symbol,
)
from atlas.portfolio.buckets import DEFAULT_BUCKET_CONFIGS, BucketConfig


@dataclass
class BucketAccount:
    """Isolated sub-account state for a single bucket."""

    bucket_id: BucketId
    cash: Money
    positions: dict[Symbol, Position] = field(default_factory=dict)
    realized_pnl: Money = field(default_factory=Money.zero)
    total_commission_paid: Money = field(default_factory=Money.zero)
    total_fees_paid: Money = field(default_factory=Money.zero)

    def market_value(self, current_prices: dict[Symbol, Decimal]) -> Money:
        """Calculate aggregate market value of all open positions in this bucket."""
        mv = Money.zero(self.cash.currency)
        for sym, pos in self.positions.items():
            price = current_prices.get(sym, pos.avg_price)
            pos_mv = Money(price * pos.qty, self.cash.currency)
            mv = mv + pos_mv
        return mv

    def unrealized_pnl(self, current_prices: dict[Symbol, Decimal]) -> Money:
        """Calculate total unrealized PnL across all open positions in this bucket."""
        unrealized = Money.zero(self.cash.currency)
        for sym, pos in self.positions.items():
            price = current_prices.get(sym, pos.avg_price)
            diff = (price - pos.avg_price) * pos.qty
            unrealized = unrealized + Money(diff, self.cash.currency)
        return unrealized

    def equity(self, current_prices: dict[Symbol, Decimal]) -> Money:
        """Calculate total equity (cash + market value) of this bucket."""
        return self.cash + self.market_value(current_prices)


class BucketLedger:
    """Multi-bucket portfolio ledger maintaining isolated sub-accounts without cross-borrowing."""

    def __init__(
        self,
        currency: str = "USD",
        configs: dict[BucketId, BucketConfig] | None = None,
    ) -> None:
        self.currency = currency
        self.configs = configs or DEFAULT_BUCKET_CONFIGS
        self.accounts: dict[BucketId, BucketAccount] = {
            b_id: BucketAccount(bucket_id=b_id, cash=Money.zero(currency)) for b_id in BucketId
        }

    def deposit(
        self,
        amount: Money,
        allocations: dict[BucketId, Decimal] | None = None,
    ) -> None:
        """Deposit cash into bucket accounts split by target allocation percentages."""
        if amount.currency != self.currency:
            raise ValueError(
                f"Deposit currency {amount.currency} does not match ledger currency {self.currency}"
            )
        if amount.amount <= Decimal("0"):
            raise ValueError("Deposit amount must be strictly positive")

        target_allocs = allocations or {
            b_id: cfg.target_allocation for b_id, cfg in self.configs.items()
        }

        # Validate allocations sum to 1.0
        total_alloc = sum(target_allocs.values(), Decimal("0"))
        if abs(total_alloc - Decimal("1.0")) > Decimal("0.0001"):
            raise ValueError(f"Bucket allocations must sum to 1.0, got {total_alloc}")

        allocated_so_far = Money.zero(self.currency)
        sorted_buckets = sorted(target_allocs.keys(), key=lambda b: target_allocs[b], reverse=True)

        for i, b_id in enumerate(sorted_buckets):
            if i == len(sorted_buckets) - 1:
                # Assign remaining cents to last bucket to ensure exact conservation
                bucket_share = amount - allocated_so_far
            else:
                share_dec = (amount.amount * target_allocs[b_id]).quantize(Decimal("0.01"))
                bucket_share = Money(share_dec, self.currency)
                allocated_so_far = allocated_so_far + bucket_share

            self.accounts[b_id].cash = self.accounts[b_id].cash + bucket_share

    def transfer(self, from_bucket: BucketId, to_bucket: BucketId, amount: Money) -> None:
        """Explicit inter-bucket rebalancing transfer."""
        if amount.currency != self.currency:
            raise ValueError("Transfer currency mismatch")
        if amount.amount <= Decimal("0"):
            raise ValueError("Transfer amount must be positive")
        if self.accounts[from_bucket].cash < amount:
            raise InsufficientCashError(
                f"Bucket {from_bucket} has insufficient cash ({self.accounts[from_bucket].cash}) "
                f"for transfer of {amount}"
            )
        self.accounts[from_bucket].cash = self.accounts[from_bucket].cash - amount
        self.accounts[to_bucket].cash = self.accounts[to_bucket].cash + amount

    def execute_fill(
        self,
        fill: Fill,
        bucket: BucketId,
        side: Side,
        symbol: Symbol,
        stop_px: Decimal | None = None,
        allow_short: bool = True,
    ) -> Position | None:
        """Process an execution fill against the designated isolated bucket sub-account with long/short support."""
        account = self.accounts[bucket]
        fill_cost = Money(fill.price * fill.qty, self.currency)
        fill_fees = fill.commission + fill.fees

        account.total_commission_paid = account.total_commission_paid + fill.commission
        account.total_fees_paid = account.total_fees_paid + fill.fees

        existing = account.positions.get(symbol)

        if side == Side.BUY:
            if existing is not None and existing.qty < 0:
                # Covering existing short position
                short_qty_held = abs(existing.qty)
                cover_qty = min(short_qty_held, fill.qty)
                cover_outlay = (
                    Money(fill.price * Decimal(cover_qty), self.currency)
                    + fill.commission
                    + fill.fees
                )

                if account.cash < cover_outlay:
                    raise InsufficientCashError(
                        f"Bucket {bucket} has {account.cash} cash, but covering short requires {cover_outlay}"
                    )
                account.cash = account.cash - cover_outlay

                entry_fee_share = (
                    existing.open_fees.amount * (Decimal(cover_qty) / Decimal(short_qty_held))
                    if existing.open_fees.amount > Decimal("0")
                    else Decimal("0")
                )
                close_fee_share = (
                    fill_fees.amount * (Decimal(cover_qty) / Decimal(fill.qty))
                    if fill.qty > 0
                    else fill_fees.amount
                )

                # Short realized P&L: (entry price - exit price) * covered_qty - entry_fees - close_fees
                short_pnl = (
                    Money((existing.avg_price - fill.price) * Decimal(cover_qty), self.currency)
                    - Money(entry_fee_share, self.currency)
                    - Money(close_fee_share, self.currency)
                )
                account.realized_pnl = account.realized_pnl + short_pnl

                remaining_short = short_qty_held - cover_qty
                if remaining_short == 0:
                    del account.positions[symbol]
                    # If buy quantity exceeded short position, open long with remaining
                    excess_long = fill.qty - cover_qty
                    if excess_long > 0:
                        long_outlay = Money(fill.price * Decimal(excess_long), self.currency)
                        if account.cash < long_outlay:
                            raise InsufficientCashError(
                                f"Bucket {bucket} cash insufficient for excess long entry"
                            )
                        account.cash = account.cash - long_outlay
                        excess_long_open_fees = (
                            fill_fees * (Decimal(excess_long) / Decimal(fill.qty))
                            if fill.qty > 0
                            else fill_fees
                        )
                        new_long = Position(
                            symbol=symbol,
                            bucket=bucket,
                            qty=Quantity(excess_long),
                            avg_price=fill.price,
                            opened_ts=fill.ts,
                            unrealized=Money.zero(self.currency),
                            realized=Money.zero(self.currency),
                            stop_px=stop_px,
                            open_fees=excess_long_open_fees,
                        )
                        account.positions[symbol] = new_long
                        return new_long
                    return None
                else:
                    rem_open_fees = existing.open_fees - Money(entry_fee_share, self.currency)
                    updated_pos = Position(
                        symbol=symbol,
                        bucket=bucket,
                        qty=Quantity(-remaining_short),
                        avg_price=existing.avg_price,
                        opened_ts=existing.opened_ts,
                        unrealized=Money.zero(self.currency),
                        realized=existing.realized + short_pnl,
                        stop_px=stop_px or existing.stop_px,
                        open_fees=rem_open_fees,
                    )
                    account.positions[symbol] = updated_pos
                    return updated_pos
            else:
                # Regular Long Buy
                total_outlay = fill_cost + fill.commission + fill.fees
                if account.cash < total_outlay:
                    raise InsufficientCashError(
                        f"Bucket {bucket} has {account.cash} cash, but buy requires {total_outlay} "
                        f"(strictly no inter-bucket borrowing allowed)"
                    )
                account.cash = account.cash - total_outlay

                if existing is not None and existing.qty > 0:
                    new_qty = existing.qty + fill.qty
                    total_spent = (existing.avg_price * Decimal(existing.qty)) + (
                        fill.price * Decimal(fill.qty)
                    )
                    new_avg_price = total_spent / Decimal(new_qty)
                    updated_pos = Position(
                        symbol=symbol,
                        bucket=bucket,
                        qty=Quantity(new_qty),
                        avg_price=new_avg_price,
                        opened_ts=existing.opened_ts,
                        unrealized=existing.unrealized,
                        realized=existing.realized,
                        stop_px=stop_px or existing.stop_px,
                        open_fees=existing.open_fees + fill_fees,
                    )
                    account.positions[symbol] = updated_pos
                    return updated_pos
                else:
                    new_pos = Position(
                        symbol=symbol,
                        bucket=bucket,
                        qty=Quantity(fill.qty),
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero(self.currency),
                        realized=Money.zero(self.currency),
                        stop_px=stop_px,
                        open_fees=fill_fees,
                    )
                    account.positions[symbol] = new_pos
                    return new_pos

        elif side == Side.SELL:
            if existing is not None and existing.qty > 0:
                # Closing/reducing existing long position
                sold_qty = min(existing.qty, fill.qty)
                proceeds = (
                    Money(fill.price * Decimal(sold_qty), self.currency)
                    - fill.commission
                    - fill.fees
                )
                account.cash = account.cash + proceeds

                entry_fee_share = (
                    existing.open_fees.amount * (Decimal(sold_qty) / Decimal(existing.qty))
                    if existing.open_fees.amount > Decimal("0")
                    else Decimal("0")
                )
                close_fee_share = (
                    fill_fees.amount * (Decimal(sold_qty) / Decimal(fill.qty))
                    if fill.qty > 0
                    else fill_fees.amount
                )

                price_gain = fill.price - existing.avg_price
                chunk_pnl = (
                    Money(price_gain * Decimal(sold_qty), self.currency)
                    - Money(entry_fee_share, self.currency)
                    - Money(close_fee_share, self.currency)
                )
                account.realized_pnl = account.realized_pnl + chunk_pnl

                remaining_qty = existing.qty - sold_qty
                if remaining_qty == 0:
                    del account.positions[symbol]
                    # If sell quantity exceeded long, open short for excess if permitted
                    excess_short = fill.qty - sold_qty
                    if excess_short > 0 and allow_short and bucket == BucketId.SWING:
                        short_proceeds = Money(fill.price * Decimal(excess_short), self.currency)
                        account.cash = account.cash + short_proceeds
                        excess_short_open_fees = (
                            fill_fees * (Decimal(excess_short) / Decimal(fill.qty))
                            if fill.qty > 0
                            else fill_fees
                        )
                        new_short = Position(
                            symbol=symbol,
                            bucket=bucket,
                            qty=Quantity(-excess_short),
                            avg_price=fill.price,
                            opened_ts=fill.ts,
                            unrealized=Money.zero(self.currency),
                            realized=Money.zero(self.currency),
                            stop_px=stop_px,
                            open_fees=excess_short_open_fees,
                        )
                        account.positions[symbol] = new_short
                        return new_short
                    return None
                else:
                    rem_open_fees = existing.open_fees - Money(entry_fee_share, self.currency)
                    updated_pos = Position(
                        symbol=symbol,
                        bucket=bucket,
                        qty=Quantity(remaining_qty),
                        avg_price=existing.avg_price,
                        opened_ts=existing.opened_ts,
                        unrealized=existing.unrealized,
                        realized=existing.realized + chunk_pnl,
                        stop_px=existing.stop_px,
                        open_fees=rem_open_fees,
                    )
                    account.positions[symbol] = updated_pos
                    return updated_pos
            elif allow_short and bucket == BucketId.SWING:
                # Open or add to short position
                proceeds = fill_cost - fill.commission - fill.fees
                account.cash = account.cash + proceeds

                if existing is not None and existing.qty < 0:
                    old_short_qty = abs(existing.qty)
                    new_short_qty = old_short_qty + fill.qty
                    total_short_cost = (existing.avg_price * Decimal(old_short_qty)) + (
                        fill.price * Decimal(fill.qty)
                    )
                    new_avg_px = total_short_cost / Decimal(new_short_qty)
                    updated_pos = Position(
                        symbol=symbol,
                        bucket=bucket,
                        qty=Quantity(-new_short_qty),
                        avg_price=new_avg_px,
                        opened_ts=existing.opened_ts,
                        unrealized=existing.unrealized,
                        realized=existing.realized,
                        stop_px=stop_px or existing.stop_px,
                        open_fees=existing.open_fees + fill_fees,
                    )
                    account.positions[symbol] = updated_pos
                    return updated_pos
                else:
                    new_short = Position(
                        symbol=symbol,
                        bucket=bucket,
                        qty=Quantity(-fill.qty),
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero(self.currency),
                        realized=Money.zero(self.currency),
                        stop_px=stop_px,
                        open_fees=fill_fees,
                    )
                    account.positions[symbol] = new_short
                    return new_short
            else:
                raise ValueError(
                    f"Cannot execute SELL for {symbol} in bucket {bucket}: position not found and shorting disabled"
                )

    def total_cash(self) -> Money:
        """Aggregate cash across all buckets."""
        total = Money.zero(self.currency)
        for acc in self.accounts.values():
            total = total + acc.cash
        return total

    def total_equity(self, current_prices: dict[Symbol, Decimal]) -> Money:
        """Aggregate total equity across all buckets."""
        total = Money.zero(self.currency)
        for acc in self.accounts.values():
            total = total + acc.equity(current_prices)
        return total

    def bucket_equity(self, bucket: BucketId, current_prices: dict[Symbol, Decimal]) -> Money:
        """Get equity for a specific bucket."""
        return self.accounts[bucket].equity(current_prices)

    def bucket_allocation(self, bucket: BucketId, current_prices: dict[Symbol, Decimal]) -> Decimal:
        """Calculate current weight of a bucket relative to total equity."""
        total = self.total_equity(current_prices)
        if total.amount == Decimal("0"):
            return Decimal("0.0")
        b_equity = self.bucket_equity(bucket, current_prices)
        return b_equity.amount / total.amount

    def all_positions(self) -> list[Position]:
        """Return list of all open positions across all buckets."""
        result: list[Position] = []
        for acc in self.accounts.values():
            result.extend(acc.positions.values())
        return result

    def positions_for_bucket(self, bucket: BucketId) -> list[Position]:
        """Return list of open positions for a specific bucket."""
        return list(self.accounts[bucket].positions.values())

    def account_state(self, ts: datetime, current_prices: dict[Symbol, Decimal]) -> AccountState:
        """Produce an immutable snapshot of total account state."""
        tot_eq = self.total_equity(current_prices)
        tot_cash = self.total_cash()
        per_b = {b_id: acc.equity(current_prices) for b_id, acc in self.accounts.items()}
        return AccountState(
            ts=ts,
            total_equity=tot_eq,
            cash=tot_cash,
            buying_power=tot_cash,
            per_bucket_equity=per_b,
        )

    def check_rebalance_needed(self, current_prices: dict[Symbol, Decimal]) -> dict[BucketId, bool]:
        """Check if any bucket has breached its target allocation rebalance band."""
        rebalance_flags: dict[BucketId, bool] = {}
        for b_id, cfg in self.configs.items():
            if b_id == BucketId.CASH:
                rebalance_flags[b_id] = False
                continue
            alloc = self.bucket_allocation(b_id, current_prices)
            rebalance_flags[b_id] = alloc < cfg.min_allocation or alloc > cfg.max_allocation
        return rebalance_flags

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete ledger state for crash recovery persistence."""
        return {
            "currency": self.currency,
            "accounts": {
                b_id.value: {
                    "cash": str(acc.cash.amount),
                    "realized_pnl": str(acc.realized_pnl.amount),
                    "total_commission_paid": str(acc.total_commission_paid.amount),
                    "total_fees_paid": str(acc.total_fees_paid.amount),
                    "positions": {
                        sym: {
                            "symbol": pos.symbol,
                            "bucket": pos.bucket.value,
                            "qty": pos.qty,
                            "avg_price": str(pos.avg_price),
                            "opened_ts": pos.opened_ts.isoformat(),
                            "stop_px": str(pos.stop_px) if pos.stop_px is not None else None,
                            "open_fees": str(pos.open_fees.amount),
                        }
                        for sym, pos in acc.positions.items()
                    },
                }
                for b_id, acc in self.accounts.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BucketLedger:
        """Reconstitute ledger state from serialized dictionary."""
        currency = data.get("currency", "USD")
        ledger = cls(currency=currency)
        for b_str, acc_data in data.get("accounts", {}).items():
            b_id = BucketId(b_str)
            acc = ledger.accounts[b_id]
            acc.cash = Money(Decimal(acc_data["cash"]), currency)
            acc.realized_pnl = Money(Decimal(acc_data.get("realized_pnl", "0")), currency)
            acc.total_commission_paid = Money(
                Decimal(acc_data.get("total_commission_paid", "0")), currency
            )
            acc.total_fees_paid = Money(Decimal(acc_data.get("total_fees_paid", "0")), currency)
            acc.positions = {}
            for sym_str, p_data in acc_data.get("positions", {}).items():
                opened_ts = datetime.fromisoformat(p_data["opened_ts"])
                if opened_ts.tzinfo is None:
                    opened_ts = opened_ts.replace(tzinfo=UTC)
                open_fees_val = Money(Decimal(p_data.get("open_fees", "0.0000")), currency)
                pos = Position(
                    symbol=Symbol(p_data["symbol"]),
                    bucket=b_id,
                    qty=Quantity(p_data["qty"]),
                    avg_price=Decimal(p_data["avg_price"]),
                    opened_ts=opened_ts,
                    unrealized=Money.zero(currency),
                    realized=Money.zero(currency),
                    stop_px=Decimal(p_data["stop_px"]) if p_data.get("stop_px") else None,
                    open_fees=open_fees_val,
                )
                acc.positions[Symbol(sym_str)] = pos
        return ledger
