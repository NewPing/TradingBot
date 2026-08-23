"""SimBroker: Simulated execution venue implementing the Broker protocol."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from atlas.backtest.costs import DefaultCostModelV1
from atlas.core.money import Money
from atlas.core.types import (
    AccountState,
    Bar,
    BrokerOrderRef,
    BucketId,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Symbol,
    TimeInForce,
)


class SimBroker:
    """Deterministic simulated broker with realistic execution and pessimistic costs.

    Key Invariants:
    1. Fill Timing: Orders submitted during bar t cannot fill until bar t+1.
    2. Exact Money Arithmetic: All financial mutations use strict Decimal-backed Money.
    3. Pessimistic Cost Model: Applies slippage, half-spread, and regulatory fees.
    """

    def __init__(
        self,
        initial_capital: Money | None = None,
        cost_model: DefaultCostModelV1 | None = None,
    ) -> None:
        self._initial_capital = initial_capital or Money(Decimal("100000.00"), "USD")
        self._cash = self._initial_capital
        self._cost_model = cost_model or DefaultCostModelV1()

        self._pending_orders: list[Order] = []
        self._order_history: dict[str, Order] = {}
        self._positions: dict[Symbol, Position] = {}
        self._fills: list[Fill] = []
        self._fill_callbacks: list[Callable[[Fill], None]] = []

    @property
    def cash(self) -> Money:
        return self._cash

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    def submit(self, order: Order) -> BrokerOrderRef:
        """Submit an order. Placed in pending queue to be executed on bar t+1."""
        submitted_order = replace(order, status=OrderStatus.SUBMITTED)
        self._pending_orders.append(submitted_order)
        self._order_history[submitted_order.id] = submitted_order
        return BrokerOrderRef(submitted_order.id)

    def cancel(self, ref: BrokerOrderRef) -> None:
        """Cancel a pending order if not yet filled."""
        self._pending_orders = [o for o in self._pending_orders if o.id != str(ref)]
        if str(ref) in self._order_history:
            self._order_history[str(ref)] = replace(
                self._order_history[str(ref)], status=OrderStatus.CANCELED
            )

    def positions(self) -> list[Position]:
        """Return all open non-zero positions."""
        return [p for p in self._positions.values() if p.qty != 0]

    def get_position(self, symbol: Symbol) -> Position | None:
        """Get position for a specific symbol."""
        pos = self._positions.get(symbol)
        if pos is not None and pos.qty != 0:
            return pos
        return None

    def account(self) -> AccountState:
        """Return current account snapshot."""
        now_ts = datetime.now()  # Fallback timestamp if not tracking clock directly
        if self._fills:
            now_ts = self._fills[-1].ts

        per_bucket: dict[BucketId, Money] = {
            BucketId.CORE: Money.zero("USD"),
            BucketId.SWING: Money.zero("USD"),
            BucketId.MOONSHOT: Money.zero("USD"),
            BucketId.CASH: self._cash,
        }

        total_market_value = Money.zero("USD")
        for pos in self.positions():
            pos_val = Money(Decimal(pos.qty) * pos.avg_price, "USD") + pos.unrealized
            per_bucket[pos.bucket] = per_bucket.get(pos.bucket, Money.zero("USD")) + pos_val
            total_market_value += pos_val

        total_equity = self._cash + total_market_value

        return AccountState(
            ts=now_ts,
            total_equity=total_equity,
            cash=self._cash,
            buying_power=self._cash,
            per_bucket_equity=per_bucket,
        )

    def on_fill(self, cb: Callable[[Fill], None]) -> None:
        """Register a callback invoked whenever a fill occurs."""
        self._fill_callbacks.append(cb)

    def is_healthy(self) -> bool:
        return True

    def process_pending_orders(
        self,
        current_ts: datetime,
        current_bars: dict[Symbol, Bar],
        daily_vols: dict[Symbol, Decimal] | None = None,
        advs: dict[Symbol, Decimal] | None = None,
    ) -> list[Fill]:
        """Process pending orders against the current bar t+1 prices.

        Orders submitted on bar t are executed using bar t+1 open (or close) price.
        """
        daily_vols = daily_vols or {}
        advs = advs or {}
        new_fills: list[Fill] = []
        remaining_pending: list[Order] = []

        # Process each pending order
        for order in self._pending_orders:
            # Check if order was created prior to current_ts (strictly t+1 enforcement)
            if order.created_ts >= current_ts:
                # Placed on current_ts -> cannot fill until NEXT bar
                remaining_pending.append(order)
                continue

            bar = current_bars.get(order.symbol)
            if bar is None:
                # No market data on this bar -> keep pending
                remaining_pending.append(order)
                continue

            # Determine execution candidate price
            base_price: Decimal
            if order.type == OrderType.MARKET:
                # Market orders fill at open of bar t+1
                base_price = bar.open
            elif order.type == OrderType.LIMIT:
                if order.limit_px is None:
                    remaining_pending.append(order)
                    continue
                # For Buy Limit: fills if low <= limit_px
                if order.side == Side.BUY and bar.low <= order.limit_px:
                    base_price = min(bar.open, order.limit_px)
                # For Sell Limit: fills if high >= limit_px
                elif order.side == Side.SELL and bar.high >= order.limit_px:
                    base_price = max(bar.open, order.limit_px)
                else:
                    remaining_pending.append(order)
                    continue
            else:
                base_price = bar.open

            adv = advs.get(order.symbol, Decimal(bar.volume) * bar.close)
            vol = daily_vols.get(order.symbol, Decimal("0.02"))

            cost_res = self._cost_model.evaluate_fill(
                side=order.side,
                qty=order.qty,
                base_price=base_price,
                adv_usd=adv,
                daily_vol=vol,
            )

            fill = Fill(
                order_id=order.id,
                ts=current_ts,
                qty=order.qty,
                price=cost_res.fill_price,
                commission=cost_res.commission,
                fees=cost_res.regulatory_fees,
                slippage_est=Money(cost_res.slippage * Decimal(order.qty), "USD"),
                venue="SIM",
            )

            self._apply_fill(order, fill)
            self._order_history[order.id] = replace(order, status=OrderStatus.FILLED)
            new_fills.append(fill)

            for cb in self._fill_callbacks:
                cb(fill)

        self._pending_orders = remaining_pending
        return new_fills

    def process_stops(
        self,
        current_ts: datetime,
        current_bars: dict[Symbol, Bar],
        daily_vols: dict[Symbol, Decimal] | None = None,
        advs: dict[Symbol, Decimal] | None = None,
    ) -> list[Fill]:
        """Check open positions for stop-loss breaches on bar t+1 (long and short)."""
        daily_vols = daily_vols or {}
        advs = advs or {}
        stop_fills: list[Fill] = []

        for symbol, pos in list(self._positions.items()):
            if pos.qty == 0 or pos.stop_px is None:
                continue

            bar = current_bars.get(symbol)
            if bar is None:
                continue

            breached = False
            base_price = pos.stop_px
            order_side = Side.SELL

            if pos.qty > 0:
                # Long position: stop breached if bar.low <= stop_px
                if bar.low <= pos.stop_px:
                    breached = True
                    order_side = Side.SELL
                    base_price = bar.open if bar.open < pos.stop_px else pos.stop_px
            else:
                # Short position (qty < 0): stop breached if bar.high >= stop_px
                if bar.high >= pos.stop_px:
                    breached = True
                    order_side = Side.BUY
                    base_price = bar.open if bar.open > pos.stop_px else pos.stop_px

            if breached:
                abs_qty = abs(pos.qty)
                adv = advs.get(symbol, Decimal(bar.volume) * bar.close)
                vol = daily_vols.get(symbol, Decimal("0.02"))

                cost_res = self._cost_model.evaluate_fill(
                    side=order_side,
                    qty=abs_qty,
                    base_price=base_price,
                    adv_usd=adv,
                    daily_vol=vol,
                )

                stop_order_id = f"stop_{symbol}_{uuid.uuid4().hex[:8]}"
                fill = Fill(
                    order_id=stop_order_id,
                    ts=current_ts,
                    qty=abs_qty,
                    price=cost_res.fill_price,
                    commission=cost_res.commission,
                    fees=cost_res.regulatory_fees,
                    slippage_est=Money(cost_res.slippage * Decimal(abs_qty), "USD"),
                    venue="SIM_STOP",
                )

                dummy_order = Order(
                    id=stop_order_id,
                    run_id="sim_run",
                    strategy_version_id="sim_strat",
                    bucket=pos.bucket,
                    symbol=symbol,
                    side=order_side,
                    qty=abs_qty,
                    type=OrderType.STOP,
                    tif=order_tif_day(),
                    created_ts=current_ts,
                    status=OrderStatus.FILLED,
                )
                self._apply_fill(dummy_order, fill)
                stop_fills.append(fill)

                for cb in self._fill_callbacks:
                    cb(fill)

        return stop_fills

    def _apply_fill(self, order: Order, fill: Fill) -> None:
        """Update cash, realized PnL, and open position following a fill."""
        fill_notional = Money(Decimal(fill.qty) * fill.price, "USD")
        existing_pos = self._positions.get(order.symbol)

        if order.side == Side.BUY:
            if existing_pos is not None and existing_pos.qty < 0:
                # Covering short position
                short_held = abs(existing_pos.qty)
                cover_qty = min(short_held, fill.qty)
                cover_outlay = (
                    Money(Decimal(cover_qty) * fill.price, "USD") + fill.commission + fill.fees
                )
                self._cash -= cover_outlay

                realized_pnl = (
                    (existing_pos.avg_price - fill.price) * Decimal(cover_qty)
                    - fill.commission.amount
                    - fill.fees.amount
                )
                new_realized = existing_pos.realized + Money(realized_pnl, "USD")

                remaining_short = short_held - cover_qty
                if remaining_short == 0:
                    del self._positions[order.symbol]
                    excess_long = fill.qty - cover_qty
                    if excess_long > 0:
                        self._cash -= Money(Decimal(excess_long) * fill.price, "USD")
                        self._positions[order.symbol] = Position(
                            symbol=order.symbol,
                            bucket=order.bucket,
                            qty=excess_long,
                            avg_price=fill.price,
                            opened_ts=fill.ts,
                            unrealized=Money.zero("USD"),
                            realized=Money.zero("USD"),
                            stop_px=order.stop_px,
                        )
                else:
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=existing_pos.bucket,
                        qty=-remaining_short,
                        avg_price=existing_pos.avg_price,
                        opened_ts=existing_pos.opened_ts,
                        unrealized=Money.zero("USD"),
                        realized=new_realized,
                        stop_px=order.stop_px or existing_pos.stop_px,
                    )
            else:
                # Long buy
                total_cash_out = fill_notional + fill.commission + fill.fees
                self._cash -= total_cash_out

                if existing_pos is None or existing_pos.qty == 0:
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=order.bucket,
                        qty=fill.qty,
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero("USD"),
                        realized=Money.zero("USD"),
                        stop_px=order.stop_px,
                    )
                else:
                    old_qty = existing_pos.qty
                    new_qty = old_qty + fill.qty
                    total_cost = (Decimal(old_qty) * existing_pos.avg_price) + (
                        Decimal(fill.qty) * fill.price
                    )
                    new_avg_px = total_cost / Decimal(new_qty)

                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=existing_pos.bucket,
                        qty=new_qty,
                        avg_price=new_avg_px,
                        opened_ts=existing_pos.opened_ts,
                        unrealized=existing_pos.unrealized,
                        realized=existing_pos.realized,
                        stop_px=order.stop_px or existing_pos.stop_px,
                    )
        else:  # SELL
            if existing_pos is not None and existing_pos.qty > 0:
                proceeds = fill_notional - fill.commission - fill.fees
                self._cash += proceeds

                sold_qty = min(existing_pos.qty, fill.qty)
                cost_basis = Decimal(sold_qty) * existing_pos.avg_price
                realized_pnl = (
                    (Decimal(sold_qty) * fill.price)
                    - cost_basis
                    - fill.commission.amount
                    - fill.fees.amount
                )
                new_realized = existing_pos.realized + Money(realized_pnl, "USD")

                remaining_qty = existing_pos.qty - sold_qty
                if remaining_qty == 0:
                    del self._positions[order.symbol]
                    excess_short = fill.qty - sold_qty
                    if excess_short > 0:
                        self._positions[order.symbol] = Position(
                            symbol=order.symbol,
                            bucket=order.bucket,
                            qty=-excess_short,
                            avg_price=fill.price,
                            opened_ts=fill.ts,
                            unrealized=Money.zero("USD"),
                            realized=Money.zero("USD"),
                            stop_px=order.stop_px,
                        )
                else:
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=existing_pos.bucket,
                        qty=remaining_qty,
                        avg_price=existing_pos.avg_price,
                        opened_ts=existing_pos.opened_ts,
                        unrealized=Money.zero("USD"),
                        realized=new_realized,
                        stop_px=existing_pos.stop_px,
                    )
            else:
                # Open or add to short position
                proceeds = fill_notional - fill.commission - fill.fees
                self._cash += proceeds

                if existing_pos is not None and existing_pos.qty < 0:
                    old_short = abs(existing_pos.qty)
                    new_short = old_short + fill.qty
                    tot_val = (existing_pos.avg_price * Decimal(old_short)) + (
                        fill.price * Decimal(fill.qty)
                    )
                    new_avg = tot_val / Decimal(new_short)
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=existing_pos.bucket,
                        qty=-new_short,
                        avg_price=new_avg,
                        opened_ts=existing_pos.opened_ts,
                        unrealized=Money.zero("USD"),
                        realized=existing_pos.realized,
                        stop_px=order.stop_px or existing_pos.stop_px,
                    )
                else:
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=order.bucket,
                        qty=-fill.qty,
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero("USD"),
                        realized=Money.zero("USD"),
                        stop_px=order.stop_px,
                    )

        self._fills.append(fill)

        self._fills.append(fill)

    def update_positions_unrealized(self, current_bars: dict[Symbol, Bar]) -> None:
        """Update mark-to-market unrealized PnL for all open positions."""
        for symbol, pos in list(self._positions.items()):
            bar = current_bars.get(symbol)
            if bar is None or pos.qty == 0:
                continue

            current_value = Decimal(pos.qty) * bar.close
            cost_basis = Decimal(pos.qty) * pos.avg_price
            unrealized_amount = current_value - cost_basis

            self._positions[symbol] = replace(
                pos,
                unrealized=Money(unrealized_amount, "USD"),
            )


def order_tif_day() -> TimeInForce:
    return TimeInForce.DAY
