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
from atlas.portfolio.ledger import BucketLedger


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
        self._realized_pnl = Money.zero("USD")

        self._pending_orders: list[Order] = []
        self._order_history: dict[str, Order] = {}
        self._positions: dict[Symbol, Position] = {}
        self._fills: list[Fill] = []
        self._fill_callbacks: list[Callable[[Fill], None]] = []

    @property
    def cash(self) -> Money:
        return self._cash

    @property
    def realized_pnl(self) -> Money:
        return self._realized_pnl

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

    def to_ledger(self, current_prices: dict[Symbol, Decimal] | None = None) -> BucketLedger:
        """Convert current SimBroker state into a BucketLedger for risk validation."""
        _ = current_prices
        ledger = BucketLedger(currency=self._cash.currency)
        if self._cash.amount > Decimal("0"):
            ledger.deposit(self._cash)
        for sym, pos in self._positions.items():
            if pos.qty != 0:
                ledger.accounts[pos.bucket].positions[sym] = pos
        return ledger

    def process_pending_orders(
        self,
        current_ts: datetime,
        current_bars: dict[Symbol, Bar],
        daily_vols: dict[Symbol, Decimal] | None = None,
        advs: dict[Symbol, Decimal] | None = None,
    ) -> list[Fill]:
        """Process pending orders against the current bar t+1 prices.

        Orders submitted on bar t are executed using bar t+1 open (or close) price.
        Sells and short covers are processed before new buys to properly release cash.
        """
        daily_vols = daily_vols or {}
        advs = advs or {}
        new_fills: list[Fill] = []
        remaining_pending: list[Order] = []

        # Partition orders into executable vs future
        executable: list[Order] = []
        for order in self._pending_orders:
            if order.created_ts >= current_ts:
                remaining_pending.append(order)
            else:
                executable.append(order)

        # Prioritize orders that free up cash (sells of long positions and buys covering short positions)
        def _exec_order_priority(ord_item: Order) -> int:
            existing = self._positions.get(ord_item.symbol)
            if ord_item.side == Side.SELL and existing is not None and existing.qty > 0:
                return 0  # Closing long position -> releases cash
            if ord_item.side == Side.BUY and existing is not None and existing.qty < 0:
                return 1  # Covering short position
            return 2  # New long entry or opening short

        executable.sort(key=_exec_order_priority)

        # Process each executable pending order
        for order in executable:
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
            elif order.type == OrderType.STOP:
                if order.stop_px is None:
                    remaining_pending.append(order)
                    continue
                # For Sell Stop: triggered if low <= stop_px
                if order.side == Side.SELL and bar.low <= order.stop_px:
                    base_price = bar.open if bar.open < order.stop_px else order.stop_px
                # For Buy Stop: triggered if high >= stop_px
                elif order.side == Side.BUY and bar.high >= order.stop_px:
                    base_price = bar.open if bar.open > order.stop_px else order.stop_px
                else:
                    remaining_pending.append(order)
                    continue
            else:
                base_price = bar.open

            adv = advs.get(order.symbol, Decimal(bar.volume) * bar.close)
            vol = daily_vols.get(order.symbol, Decimal("0.02"))

            # Available cash check for Buy orders and margin check for Short Sell orders
            effective_qty = order.qty
            existing_pos = self._positions.get(order.symbol)
            is_covering_short = existing_pos is not None and existing_pos.qty < 0
            is_opening_short = order.side == Side.SELL and (
                existing_pos is None or existing_pos.qty <= 0
            )

            if order.side == Side.BUY and not is_covering_short:
                # Approximate worst-case price for cash budget check
                approx_px = base_price * Decimal("1.01")
                comm_est = self._cost_model.calculate_commission(effective_qty, approx_px)
                fees_est = self._cost_model.calculate_regulatory_fees(
                    order.side, effective_qty, approx_px
                )
                total_est = (approx_px * Decimal(effective_qty)) + comm_est.amount + fees_est.amount

                if total_est > self._cash.amount:
                    avail = self._cash.amount - comm_est.amount - fees_est.amount
                    if avail <= Decimal("0"):
                        self._order_history[order.id] = replace(order, status=OrderStatus.CANCELED)
                        continue
                    max_shares = int(avail // approx_px)
                    if max_shares <= 0:
                        self._order_history[order.id] = replace(order, status=OrderStatus.CANCELED)
                        continue
                    effective_qty = max_shares

            elif is_opening_short:
                # Margin requirement check for opening or adding to short positions
                approx_px = base_price * Decimal("1.01")
                short_notional_est = Decimal(effective_qty) * approx_px
                account_state = self.account()
                required_margin = short_notional_est * Decimal("0.50")
                if required_margin > account_state.total_equity.amount:
                    avail_margin = account_state.total_equity.amount * Decimal("2.0")
                    if avail_margin <= Decimal("0"):
                        self._order_history[order.id] = replace(order, status=OrderStatus.CANCELED)
                        continue
                    max_shares = int(avail_margin // approx_px)
                    if max_shares <= 0:
                        self._order_history[order.id] = replace(order, status=OrderStatus.CANCELED)
                        continue
                    effective_qty = max_shares

            cost_res = self._cost_model.evaluate_fill(
                side=order.side,
                qty=effective_qty,
                base_price=base_price,
                adv_usd=adv,
                daily_vol=vol,
            )

            fill = Fill(
                order_id=order.id,
                ts=current_ts,
                qty=effective_qty,
                price=cost_res.fill_price,
                commission=cost_res.commission,
                fees=cost_res.regulatory_fees,
                slippage_est=Money(cost_res.slippage * Decimal(effective_qty), "USD"),
                venue="SIM",
                symbol=order.symbol,
                side=order.side,
            )

            self._apply_fill(order, fill)
            final_status = (
                OrderStatus.FILLED if effective_qty == order.qty else OrderStatus.PARTIALLY_FILLED
            )
            self._order_history[order.id] = replace(order, status=final_status)
            if effective_qty < order.qty and order.tif == TimeInForce.GTC:
                remaining_order = replace(order, qty=order.qty - effective_qty)
                remaining_pending.append(remaining_order)
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
                # Long position: stop breached if bar.low <= stop_px (gap fill on bar.open if gap down)
                if pos.opened_ts >= current_ts:
                    if bar.low < pos.avg_price and bar.low <= pos.stop_px:
                        breached = True
                        order_side = Side.SELL
                        base_price = bar.open if bar.open < pos.stop_px else pos.stop_px
                else:
                    if bar.low <= pos.stop_px:
                        breached = True
                        order_side = Side.SELL
                        base_price = bar.open if bar.open < pos.stop_px else pos.stop_px
            else:
                # Short position (qty < 0): stop breached if bar.high >= stop_px (gap fill on bar.open if gap up)
                if pos.opened_ts >= current_ts:
                    if bar.high > pos.avg_price and bar.high >= pos.stop_px:
                        breached = True
                        order_side = Side.BUY
                        base_price = bar.open if bar.open > pos.stop_px else pos.stop_px
                else:
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
                    symbol=symbol,
                    side=order_side,
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

        fill_fees = fill.commission + fill.fees

        if order.side == Side.BUY:
            if existing_pos is not None and existing_pos.qty < 0:
                # Covering short position
                short_held = abs(existing_pos.qty)
                cover_qty = min(short_held, fill.qty)
                cover_outlay = (
                    Money(Decimal(cover_qty) * fill.price, "USD") + fill.commission + fill.fees
                )
                self._cash -= cover_outlay

                entry_fee_share = (
                    existing_pos.open_fees.amount * (Decimal(cover_qty) / Decimal(short_held))
                    if existing_pos.open_fees.amount > Decimal("0")
                    else Decimal("0")
                )
                close_fee_share = (
                    fill_fees.amount * (Decimal(cover_qty) / Decimal(fill.qty))
                    if fill.qty > 0
                    else fill_fees.amount
                )

                realized_pnl = (
                    (existing_pos.avg_price - fill.price) * Decimal(cover_qty)
                    - entry_fee_share
                    - close_fee_share
                )
                self._realized_pnl += Money(realized_pnl, "USD")
                new_realized = existing_pos.realized + Money(realized_pnl, "USD")

                remaining_short = short_held - cover_qty
                if remaining_short == 0:
                    del self._positions[order.symbol]
                    excess_long = fill.qty - cover_qty
                    if excess_long > 0:
                        self._cash -= Money(Decimal(excess_long) * fill.price, "USD")
                        excess_long_open_fees = (
                            fill_fees * (Decimal(excess_long) / Decimal(fill.qty))
                            if fill.qty > 0
                            else fill_fees
                        )
                        self._positions[order.symbol] = Position(
                            symbol=order.symbol,
                            bucket=order.bucket,
                            qty=excess_long,
                            avg_price=fill.price,
                            opened_ts=fill.ts,
                            unrealized=Money.zero("USD"),
                            realized=Money.zero("USD"),
                            stop_px=order.stop_px,
                            open_fees=excess_long_open_fees,
                        )
                else:
                    rem_open_fees = existing_pos.open_fees - Money(entry_fee_share, "USD")
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=existing_pos.bucket,
                        qty=-remaining_short,
                        avg_price=existing_pos.avg_price,
                        opened_ts=existing_pos.opened_ts,
                        unrealized=Money.zero("USD"),
                        realized=new_realized,
                        stop_px=order.stop_px or existing_pos.stop_px,
                        open_fees=rem_open_fees,
                    )
            else:
                # Long buy
                total_cash_out = fill_notional + fill.commission + fill.fees
                self._cash -= total_cash_out

                if existing_pos is None or existing_pos.qty == 0:
                    init_stop = (
                        min(order.stop_px, fill.price * Decimal("0.999"))
                        if order.stop_px is not None
                        else None
                    )
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=order.bucket,
                        qty=fill.qty,
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero("USD"),
                        realized=Money.zero("USD"),
                        stop_px=init_stop,
                        open_fees=fill_fees,
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
                        unrealized=Money.zero("USD"),
                        realized=existing_pos.realized,
                        stop_px=order.stop_px or existing_pos.stop_px,
                        open_fees=existing_pos.open_fees + fill_fees,
                    )
        else:  # SELL
            if existing_pos is not None and existing_pos.qty > 0:
                proceeds = fill_notional - fill.commission - fill.fees
                self._cash += proceeds

                sold_qty = min(existing_pos.qty, fill.qty)
                cost_basis = Decimal(sold_qty) * existing_pos.avg_price

                entry_fee_share = (
                    existing_pos.open_fees.amount * (Decimal(sold_qty) / Decimal(existing_pos.qty))
                    if existing_pos.open_fees.amount > Decimal("0")
                    else Decimal("0")
                )
                close_fee_share = (
                    fill_fees.amount * (Decimal(sold_qty) / Decimal(fill.qty))
                    if fill.qty > 0
                    else fill_fees.amount
                )

                realized_pnl = (
                    (Decimal(sold_qty) * fill.price)
                    - cost_basis
                    - entry_fee_share
                    - close_fee_share
                )
                self._realized_pnl += Money(realized_pnl, "USD")
                new_realized = existing_pos.realized + Money(realized_pnl, "USD")

                remaining_qty = existing_pos.qty - sold_qty
                if remaining_qty == 0:
                    del self._positions[order.symbol]
                    excess_short = fill.qty - sold_qty
                    if excess_short > 0:
                        excess_short_open_fees = (
                            fill_fees * (Decimal(excess_short) / Decimal(fill.qty))
                            if fill.qty > 0
                            else fill_fees
                        )
                        self._positions[order.symbol] = Position(
                            symbol=order.symbol,
                            bucket=order.bucket,
                            qty=-excess_short,
                            avg_price=fill.price,
                            opened_ts=fill.ts,
                            unrealized=Money.zero("USD"),
                            realized=Money.zero("USD"),
                            stop_px=order.stop_px,
                            open_fees=excess_short_open_fees,
                        )
                else:
                    rem_open_fees = existing_pos.open_fees - Money(entry_fee_share, "USD")
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=existing_pos.bucket,
                        qty=remaining_qty,
                        avg_price=existing_pos.avg_price,
                        opened_ts=existing_pos.opened_ts,
                        unrealized=Money.zero("USD"),
                        realized=new_realized,
                        stop_px=existing_pos.stop_px,
                        open_fees=rem_open_fees,
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
                        open_fees=existing_pos.open_fees + fill_fees,
                    )
                else:
                    init_stop = (
                        max(order.stop_px, fill.price * Decimal("1.001"))
                        if order.stop_px is not None
                        else None
                    )
                    self._positions[order.symbol] = Position(
                        symbol=order.symbol,
                        bucket=order.bucket,
                        qty=-fill.qty,
                        avg_price=fill.price,
                        opened_ts=fill.ts,
                        unrealized=Money.zero("USD"),
                        realized=Money.zero("USD"),
                        stop_px=init_stop,
                        open_fees=fill_fees,
                    )

        self._fills.append(fill)

    def update_trailing_stops(
        self,
        current_bars: dict[Symbol, Bar],
        atrs: dict[Symbol, Decimal],
        atr_multiple: float = 3.0,
    ) -> None:
        """Update and ratchet ATR trailing stop loss levels on open positions."""
        for symbol, pos in list(self._positions.items()):
            if pos.qty == 0:
                continue
            bar = current_bars.get(symbol)
            atr_val = atrs.get(symbol)
            if bar is None or atr_val is None or atr_val <= Decimal("0"):
                continue
            stop_dist = atr_val * Decimal(str(atr_multiple))
            if pos.qty > 0:
                # Long position: ratchet stop upward only
                candidate_stop = max(Decimal("0.01"), bar.close - stop_dist)
                new_stop = max(pos.stop_px or Decimal("0.01"), candidate_stop)
                self._positions[symbol] = replace(pos, stop_px=new_stop)
            elif pos.qty < 0:
                # Short position: ratchet stop downward only
                candidate_stop = bar.close + stop_dist
                new_stop = min(pos.stop_px or (bar.close * Decimal("2.0")), candidate_stop)
                self._positions[symbol] = replace(pos, stop_px=new_stop)

    def apply_daily_carry(
        self,
        current_bars: dict[Symbol, Bar] | None = None,
        borrow_rate_annual: Decimal = Decimal("0.03"),
        cash_yield_annual: Decimal = Decimal("0.04"),
        margin_rate_annual: Decimal = Decimal("0.06"),
    ) -> tuple[Money, Money]:
        """Apply 1-day short borrow fees, margin debit interest on negative cash, and idle cash yield."""
        current_bars = current_bars or {}
        # Calculate short notional using mark-to-market price
        short_notional = Decimal("0.0")
        for pos in self.positions():
            if pos.qty < 0:
                px = current_bars[pos.symbol].close if pos.symbol in current_bars else pos.avg_price
                short_notional += Decimal(abs(pos.qty)) * px

        borrow_fee = Money.zero("USD")
        if short_notional > Decimal("0"):
            daily_borrow = (short_notional * borrow_rate_annual) / Decimal("252")
            borrow_fee = Money(daily_borrow, "USD")
            self._cash -= borrow_fee

        # Apply margin debit interest on negative cash balance
        if self._cash.amount < Decimal("0"):
            daily_margin = (abs(self._cash.amount) * margin_rate_annual) / Decimal("252")
            self._cash -= Money(daily_margin, "USD")

        # Idle cash yield is applied strictly to unencumbered cash (gross cash minus short collateral liability)
        unencumbered_cash = self._cash.amount - short_notional
        cash_yield = Money.zero("USD")
        if unencumbered_cash > Decimal("0") and cash_yield_annual > Decimal("0"):
            daily_yield = (unencumbered_cash * cash_yield_annual) / Decimal("252")
            cash_yield = Money(daily_yield, "USD")
            self._cash += cash_yield

        return borrow_fee, cash_yield

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
