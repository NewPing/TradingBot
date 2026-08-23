"""German Tax Accounting Engine (§ 20 EStG) & FIFO Tax Lot Manager (Phase 9)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.accounting.ecb import ECBRateProvider
from atlas.core.types import Side, Symbol
from atlas.data.models import TaxEvent, TaxLot

logger = logging.getLogger(__name__)

# German Tax Constants (§ 20 EStG)
KESt_RATE = Decimal("0.25")  # 25% Kapitalertragsteuer
SOLI_RATE = Decimal("0.055")  # 5.5% Solidaritätszuschlag on KESt (1.375% effective)
STANDARD_SPARERPAUSCHBETRAG = Decimal("1000.00")  # €1,000 annual tax-free allowance


@dataclass
class TaxReportSummary:
    """Annual German tax report summary across all buckets and asset classes."""

    tax_year: int
    total_realized_gains_eur: Decimal = Decimal("0.00")
    total_realized_losses_eur: Decimal = Decimal("0.00")
    net_taxable_income_eur: Decimal = Decimal("0.00")
    aktien_gains_eur: Decimal = Decimal("0.00")
    aktien_losses_eur: Decimal = Decimal("0.00")
    aktien_loss_carryforward_eur: Decimal = Decimal("0.00")
    sonstige_gains_eur: Decimal = Decimal("0.00")
    sonstige_losses_eur: Decimal = Decimal("0.00")
    sonstige_loss_carryforward_eur: Decimal = Decimal("0.00")
    sparerpauschbetrag_used_eur: Decimal = Decimal("0.00")
    sparerpauschbetrag_remaining_eur: Decimal = Decimal("1000.00")
    total_kest_eur: Decimal = Decimal("0.00")
    total_soli_eur: Decimal = Decimal("0.00")
    total_kirchensteuer_eur: Decimal = Decimal("0.00")
    total_tax_liability_eur: Decimal = Decimal("0.00")
    total_trades_processed: int = 0
    open_lots_count: int = 0
    open_lots_cost_basis_eur: Decimal = Decimal("0.00")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tax_year": self.tax_year,
            "total_realized_gains_eur": float(self.total_realized_gains_eur),
            "total_realized_losses_eur": float(self.total_realized_losses_eur),
            "net_taxable_income_eur": float(self.net_taxable_income_eur),
            "aktien_gains_eur": float(self.aktien_gains_eur),
            "aktien_losses_eur": float(self.aktien_losses_eur),
            "aktien_loss_carryforward_eur": float(self.aktien_loss_carryforward_eur),
            "sonstige_gains_eur": float(self.sonstige_gains_eur),
            "sonstige_losses_eur": float(self.sonstige_losses_eur),
            "sonstige_loss_carryforward_eur": float(self.sonstige_loss_carryforward_eur),
            "sparerpauschbetrag_used_eur": float(self.sparerpauschbetrag_used_eur),
            "sparerpauschbetrag_remaining_eur": float(self.sparerpauschbetrag_remaining_eur),
            "total_kest_eur": float(self.total_kest_eur),
            "total_soli_eur": float(self.total_soli_eur),
            "total_kirchensteuer_eur": float(self.total_kirchensteuer_eur),
            "total_tax_liability_eur": float(self.total_tax_liability_eur),
            "effective_tax_rate_pct": (
                round(
                    float(
                        (self.total_tax_liability_eur / self.net_taxable_income_eur)
                        * Decimal("100.0")
                    ),
                    2,
                )
                if self.net_taxable_income_eur > Decimal("0")
                else 0.0
            ),
            "total_trades_processed": self.total_trades_processed,
            "open_lots_count": self.open_lots_count,
            "open_lots_cost_basis_eur": float(self.open_lots_cost_basis_eur),
        }


class FIFOLotManager:
    """Manages acquisition tax lots strictly using First-In-First-Out (FIFO) rules."""

    def __init__(
        self,
        session: Session | None = None,
        ecb_provider: ECBRateProvider | None = None,
    ) -> None:
        self.session = session
        self.ecb_provider = ecb_provider or ECBRateProvider(session=session)
        self._memory_lots: dict[str, list[TaxLot]] = {}

    def process_buy(
        self,
        symbol: Symbol | str,
        qty: int,
        price: Decimal,
        ts: datetime,
        asset_category: str = "AKTIEN",
        commission_usd: Decimal = Decimal("0.0"),
        fill_id: str | None = None,
    ) -> TaxLot:
        """Create a new FIFO tax lot upon buying equity or ETF shares."""
        buy_date = ts.date() if isinstance(ts, datetime) else ts
        fx_rate = self.ecb_provider.get_rate(buy_date, "EUR", "USD")
        buy_price_usd = Decimal(str(price))
        commission_eur = (commission_usd / fx_rate).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        buy_price_eur = (
            ((buy_price_usd * Decimal(qty) + commission_usd) / (fx_rate * Decimal(qty))).quantize(
                Decimal("0.0001"), ROUND_HALF_UP
            )
            if qty > 0
            else (buy_price_usd / fx_rate).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        )
        total_cost_eur = (buy_price_eur * qty).quantize(Decimal("0.0001"), ROUND_HALF_UP)

        lot_id = f"lot_{uuid.uuid4().hex[:12]}"
        lot = TaxLot(
            id=lot_id,
            symbol=str(symbol),
            asset_category=asset_category,
            buy_fill_id=fill_id or lot_id,
            buy_date=buy_date,
            buy_ts=ts
            if isinstance(ts, datetime)
            else datetime.combine(buy_date, datetime.min.time(), tzinfo=UTC),
            quantity_initial=qty,
            quantity_remaining=qty,
            buy_price_usd=buy_price_usd,
            buy_fx_rate_eur_usd=fx_rate,
            buy_price_eur=buy_price_eur,
            total_cost_eur=total_cost_eur,
            commission_eur=commission_eur,
            status="OPEN",
            created_at=datetime.now(UTC),
        )

        if self.session is not None:
            self.session.add(lot)
            self.session.commit()
        else:
            self._memory_lots.setdefault(str(symbol), []).append(lot)

        return lot

    def get_open_lots(self, symbol: str) -> list[TaxLot]:
        """Fetch all OPEN or PARTIAL tax lots for a symbol sorted by buy_ts ascending (FIFO)."""
        if self.session is not None:
            stmt = (
                select(TaxLot)
                .where(
                    TaxLot.symbol == symbol,
                    TaxLot.status.in_(["OPEN", "PARTIAL"]),
                    TaxLot.quantity_remaining > 0,
                )
                .order_by(TaxLot.buy_ts.asc())
            )
            return list(self.session.execute(stmt).scalars().all())
        else:
            return sorted(
                [
                    lot
                    for lot in self._memory_lots.get(symbol, [])
                    if lot.status in ["OPEN", "PARTIAL"] and lot.quantity_remaining > 0
                ],
                key=lambda item: item.buy_ts,
            )

    def process_sell(
        self,
        symbol: Symbol | str,
        qty: int,
        price: Decimal,
        ts: datetime,
        commission_usd: Decimal = Decimal("0.0"),
    ) -> list[tuple[TaxLot, int, Decimal, Decimal]]:
        """Consume FIFO tax lots for a sell order.

        Returns list of (TaxLot, matched_qty, buy_cost_eur_per_share, sell_price_eur_per_share).
        """
        _ = commission_usd
        sym_str = str(symbol)
        open_lots = self.get_open_lots(sym_str)
        qty_to_fill = qty
        matched_allocations: list[tuple[TaxLot, int, Decimal, Decimal]] = []

        sell_date = ts.date() if isinstance(ts, datetime) else ts
        sell_fx_rate = self.ecb_provider.get_rate(sell_date, "EUR", "USD")
        sell_price_usd = Decimal(str(price))
        sell_price_eur = (sell_price_usd / sell_fx_rate).quantize(Decimal("0.0001"), ROUND_HALF_UP)

        for lot in open_lots:
            if qty_to_fill <= 0:
                break

            matched_qty = min(qty_to_fill, lot.quantity_remaining)
            lot.quantity_remaining -= matched_qty

            if lot.quantity_remaining == 0:
                lot.status = "CLOSED"
                lot.closed_at = (
                    ts
                    if isinstance(ts, datetime)
                    else datetime.combine(sell_date, datetime.min.time(), tzinfo=UTC)
                )
            else:
                lot.status = "PARTIAL"

            matched_allocations.append((lot, matched_qty, lot.buy_price_eur, sell_price_eur))
            qty_to_fill -= matched_qty

        if self.session is not None:
            self.session.commit()

        if qty_to_fill > 0:
            logger.warning(
                "Oversold symbol %s by %d shares with no open FIFO tax lots!", sym_str, qty_to_fill
            )

        return matched_allocations


class GermanTaxEngine:
    """Calculates Kapitalertragsteuer, Solidaritätszuschlag, and annual tax summaries."""

    def __init__(
        self,
        session: Session | None = None,
        ecb_provider: ECBRateProvider | None = None,
        sparerpauschbetrag: Decimal = STANDARD_SPARERPAUSCHBETRAG,
        church_tax_rate: Decimal = Decimal("0.0"),
    ) -> None:
        self.session = session
        self.ecb_provider = ecb_provider or ECBRateProvider(session=session)
        self.lot_manager = FIFOLotManager(session=session, ecb_provider=self.ecb_provider)
        self.sparerpauschbetrag = sparerpauschbetrag
        self.church_tax_rate = church_tax_rate
        self._memory_events: list[TaxEvent] = []

    def record_trade(
        self,
        symbol: Symbol | str,
        side: Side | str,
        qty: int,
        price: Decimal,
        ts: datetime,
        commission_usd: Decimal = Decimal("0.0"),
        asset_category: str = "AKTIEN",
        fill_id: str | None = None,
    ) -> list[TaxEvent]:
        """Record a BUY or SELL execution trade and generate taxable events upon disposition."""
        side_enum = Side(side) if isinstance(side, str) else side
        if side_enum == Side.BUY:
            self.lot_manager.process_buy(
                symbol=symbol,
                qty=qty,
                price=price,
                ts=ts,
                asset_category=asset_category,
                commission_usd=commission_usd,
                fill_id=fill_id,
            )
            return []

        # SELL disposition
        allocations = self.lot_manager.process_sell(
            symbol=symbol,
            qty=qty,
            price=price,
            ts=ts,
            commission_usd=commission_usd,
        )

        events: list[TaxEvent] = []
        sell_date = ts.date() if isinstance(ts, datetime) else ts
        sell_ts = (
            ts
            if isinstance(ts, datetime)
            else datetime.combine(sell_date, datetime.min.time(), tzinfo=UTC)
        )
        sell_fx_rate = self.ecb_provider.get_rate(sell_date, "EUR", "USD")
        sell_price_usd = Decimal(str(price))
        commission_eur = (commission_usd / sell_fx_rate).quantize(Decimal("0.0001"), ROUND_HALF_UP)

        for lot, matched_qty, buy_price_eur, sell_price_eur in allocations:
            lot_commission_eur = (
                ((commission_eur * Decimal(matched_qty)) / Decimal(qty)).quantize(
                    Decimal("0.0001"), ROUND_HALF_UP
                )
                if qty > 0
                else Decimal("0.0000")
            )
            proceeds_eur = (sell_price_eur * Decimal(matched_qty)).quantize(
                Decimal("0.0001"), ROUND_HALF_UP
            )
            cost_basis_eur = (buy_price_eur * Decimal(matched_qty)).quantize(
                Decimal("0.0001"), ROUND_HALF_UP
            )
            gain_loss_eur = (proceeds_eur - cost_basis_eur - lot_commission_eur).quantize(
                Decimal("0.0001"), ROUND_HALF_UP
            )
            is_gain = gain_loss_eur > Decimal("0")

            # Calculate German Taxes
            kest = Decimal("0.0000")
            soli = Decimal("0.0000")
            church_tax = Decimal("0.0000")

            if is_gain:
                if self.church_tax_rate > Decimal("0"):
                    denom = Decimal("1.0") + KESt_RATE * self.church_tax_rate
                    kest = ((gain_loss_eur * KESt_RATE) / denom).quantize(
                        Decimal("0.0001"), ROUND_HALF_UP
                    )
                    church_tax = (kest * self.church_tax_rate).quantize(
                        Decimal("0.0001"), ROUND_HALF_UP
                    )
                else:
                    kest = (gain_loss_eur * KESt_RATE).quantize(Decimal("0.0001"), ROUND_HALF_UP)

                soli = (kest * SOLI_RATE).quantize(Decimal("0.0001"), ROUND_HALF_UP)

            total_tax = kest + soli + church_tax
            event_id = f"txev_{uuid.uuid4().hex[:12]}"

            event = TaxEvent(
                id=event_id,
                tax_lot_id=lot.id,
                sell_fill_id=fill_id or event_id,
                symbol=str(symbol),
                asset_category=lot.asset_category,
                tax_year=sell_date.year,
                sell_date=sell_date,
                sell_ts=sell_ts,
                quantity=matched_qty,
                buy_price_eur=buy_price_eur,
                sell_price_usd=sell_price_usd,
                sell_fx_rate_eur_usd=sell_fx_rate,
                sell_price_eur=sell_price_eur,
                proceeds_eur=proceeds_eur,
                cost_basis_eur=cost_basis_eur,
                commission_eur=commission_eur,
                gain_loss_eur=gain_loss_eur,
                is_gain=is_gain,
                kest_amount_eur=kest,
                soli_amount_eur=soli,
                kirchensteuer_eur=church_tax,
                total_tax_eur=total_tax,
                created_at=datetime.now(UTC),
            )

            if self.session is not None:
                self.session.add(event)
            else:
                self._memory_events.append(event)

            events.append(event)

        if self.session is not None and events:
            self.session.commit()

        return events

    def generate_annual_tax_report(self, tax_year: int) -> TaxReportSummary:
        """Generate comprehensive annual German tax report with loss offsetting (§ 20 Abs. 6 EStG)."""
        summary = TaxReportSummary(tax_year=tax_year)

        events: list[TaxEvent]
        if self.session is not None:
            stmt = (
                select(TaxEvent)
                .where(TaxEvent.tax_year == tax_year)
                .order_by(TaxEvent.sell_ts.asc())
            )
            events = list(self.session.execute(stmt).scalars().all())
        else:
            events = [e for e in self._memory_events if e.tax_year == tax_year]

        summary.total_trades_processed = len(events)

        aktien_gains = Decimal("0.00")
        aktien_losses = Decimal("0.00")
        sonstige_gains = Decimal("0.00")
        sonstige_losses = Decimal("0.00")

        for ev in events:
            gl = Decimal(str(ev.gain_loss_eur))
            if ev.asset_category == "AKTIEN":
                if gl >= Decimal("0"):
                    aktien_gains += gl
                else:
                    aktien_losses += abs(gl)
            else:
                if gl >= Decimal("0"):
                    sonstige_gains += gl
                else:
                    sonstige_losses += abs(gl)

        summary.aktien_gains_eur = aktien_gains.quantize(Decimal("0.01"), ROUND_HALF_UP)
        summary.aktien_losses_eur = aktien_losses.quantize(Decimal("0.01"), ROUND_HALF_UP)
        summary.sonstige_gains_eur = sonstige_gains.quantize(Decimal("0.01"), ROUND_HALF_UP)
        summary.sonstige_losses_eur = sonstige_losses.quantize(Decimal("0.01"), ROUND_HALF_UP)

        summary.total_realized_gains_eur = (aktien_gains + sonstige_gains).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        summary.total_realized_losses_eur = (aktien_losses + sonstige_losses).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )

        net_aktien = aktien_gains - aktien_losses
        if net_aktien < Decimal("0"):
            summary.aktien_loss_carryforward_eur = abs(net_aktien).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )
            taxable_aktien = Decimal("0.00")
        else:
            summary.aktien_loss_carryforward_eur = Decimal("0.00")
            taxable_aktien = net_aktien

        # § 20 Abs. 6 Satz 5 EStG: Loss offsetting cap for Termingeschäfte/Shorts at €20,000 per annum
        max_deductible_sonstige_losses = min(sonstige_losses, Decimal("20000.00"))
        excess_sonstige_loss = max(Decimal("0.00"), sonstige_losses - Decimal("20000.00"))

        net_sonstige = sonstige_gains - min(sonstige_gains, max_deductible_sonstige_losses)
        summary.sonstige_loss_carryforward_eur = (
            excess_sonstige_loss
            + max(Decimal("0.00"), max_deductible_sonstige_losses - sonstige_gains)
        ).quantize(Decimal("0.01"), ROUND_HALF_UP)
        taxable_sonstige = net_sonstige

        taxable_before_allowance = taxable_aktien + taxable_sonstige

        allowance_used = min(taxable_before_allowance, self.sparerpauschbetrag)
        summary.sparerpauschbetrag_used_eur = allowance_used.quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        summary.sparerpauschbetrag_remaining_eur = (
            self.sparerpauschbetrag - allowance_used
        ).quantize(Decimal("0.01"), ROUND_HALF_UP)

        net_taxable = max(Decimal("0.00"), taxable_before_allowance - allowance_used)
        summary.net_taxable_income_eur = net_taxable.quantize(Decimal("0.01"), ROUND_HALF_UP)

        if net_taxable > Decimal("0"):
            if self.church_tax_rate > Decimal("0"):
                denom = Decimal("1.0") + KESt_RATE * self.church_tax_rate
                kest = (net_taxable * KESt_RATE) / denom
                church_tax = kest * self.church_tax_rate
            else:
                kest = net_taxable * KESt_RATE
                church_tax = Decimal("0.00")

            soli = kest * SOLI_RATE
            summary.total_kest_eur = kest.quantize(Decimal("0.01"), ROUND_HALF_UP)
            summary.total_soli_eur = soli.quantize(Decimal("0.01"), ROUND_HALF_UP)
            summary.total_kirchensteuer_eur = church_tax.quantize(Decimal("0.01"), ROUND_HALF_UP)
            summary.total_tax_liability_eur = (kest + soli + church_tax).quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )

        if self.session is not None:
            open_stmt = select(TaxLot).where(TaxLot.status.in_(["OPEN", "PARTIAL"]))
            open_lots = list(self.session.execute(open_stmt).scalars().all())
            summary.open_lots_count = len(open_lots)
            total_open_cost = sum(
                (lot.buy_price_eur * Decimal(lot.quantity_remaining) for lot in open_lots),
                Decimal("0.00"),
            )
            summary.open_lots_cost_basis_eur = total_open_cost.quantize(
                Decimal("0.01"), ROUND_HALF_UP
            )

        return summary
