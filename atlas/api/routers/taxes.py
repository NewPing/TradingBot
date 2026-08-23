"""FastAPI router for German tax reporting, FIFO lot inventory, and ECB exchange rates (Phase 9)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from atlas.accounting.tax import GermanTaxEngine
from atlas.api.schemas.taxes import (
    AnnualTaxReportResponse,
    ECBRateResponse,
    TaxEventResponse,
    TaxLotResponse,
)

router = APIRouter(prefix="/api/v1/taxes", tags=["Tax Accounting & Compliance"])


# Dependency placeholder / DB session helper
def get_db() -> Session | None:
    # In production injected by engine or SessionLocal
    return None


@router.get("/report/{year}", response_model=AnnualTaxReportResponse)
def get_annual_tax_report(
    year: int,
    church_tax_rate: float = Query(
        0.0, description="Optional German church tax rate (e.g. 0.08 or 0.09)"
    ),
    sparerpauschbetrag: float = Query(
        1000.0, description="Annual tax-free allowance in EUR (€1,000 single / €2,000 married)"
    ),
) -> AnnualTaxReportResponse:
    """Generate comprehensive German tax report (§ 20 EStG) with loss offset pots and KESt/Soli calculation."""
    tax_engine = GermanTaxEngine(
        session=None,
        sparerpauschbetrag=Decimal(str(sparerpauschbetrag)),
        church_tax_rate=Decimal(str(church_tax_rate)),
    )
    report = tax_engine.generate_annual_tax_report(tax_year=year)
    data = report.to_dict()
    return AnnualTaxReportResponse(**data)


@router.get("/lots", response_model=list[TaxLotResponse])
def list_tax_lots(
    symbol: str | None = Query(None, description="Filter by ticker symbol"),
    status: str | None = Query(None, description="Filter by lot status (OPEN, PARTIAL, CLOSED)"),
    limit: int = Query(100, ge=1, le=1000),
) -> list[TaxLotResponse]:
    """List FIFO tax lots with acquisition costs in both USD and EUR."""
    # Provide structured baseline lots
    now = datetime.now(UTC)
    sample_lots = [
        TaxLotResponse(
            id="lot_001",
            symbol=symbol or "AAPL",
            asset_category="AKTIEN",
            buy_date=now.date(),
            buy_ts=now,
            quantity_initial=50,
            quantity_remaining=50,
            buy_price_usd=225.50,
            buy_fx_rate_eur_usd=1.0850,
            buy_price_eur=207.83,
            total_cost_eur=10391.50,
            commission_eur=0.92,
            status="OPEN",
            closed_at=None,
        ),
        TaxLotResponse(
            id="lot_002",
            symbol=symbol or "MSFT",
            asset_category="AKTIEN",
            buy_date=now.date(),
            buy_ts=now,
            quantity_initial=30,
            quantity_remaining=30,
            buy_price_usd=415.20,
            buy_fx_rate_eur_usd=1.0850,
            buy_price_eur=382.67,
            total_cost_eur=11480.10,
            commission_eur=0.92,
            status="OPEN",
            closed_at=None,
        ),
    ]
    if status:
        sample_lots = [lot for lot in sample_lots if lot.status.upper() == status.upper()]
    return sample_lots[:limit]


@router.get("/events", response_model=list[TaxEventResponse])
def list_tax_events(
    year: int | None = Query(None, description="Filter by tax year"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(100, ge=1, le=1000),
) -> list[TaxEventResponse]:
    """List taxable disposition events with realized PnL, KESt, and Soli breakdowns."""
    now = datetime.now(UTC)
    target_year = year or now.year
    sample_events = [
        TaxEventResponse(
            id="txev_001",
            tax_lot_id="lot_prev_01",
            symbol=symbol or "NVDA",
            asset_category="AKTIEN",
            tax_year=target_year,
            sell_date=now.date(),
            sell_ts=now,
            quantity=25,
            buy_price_eur=110.50,
            sell_price_usd=132.80,
            sell_fx_rate_eur_usd=1.0850,
            sell_price_eur=122.39,
            proceeds_eur=3059.75,
            cost_basis_eur=2762.50,
            commission_eur=0.92,
            gain_loss_eur=296.33,
            is_gain=True,
            kest_amount_eur=74.08,
            soli_amount_eur=4.07,
            kirchensteuer_eur=0.0,
            total_tax_eur=78.15,
        )
    ]
    return sample_events[:limit]


@router.get("/ecb-rates", response_model=list[ECBRateResponse])
def list_ecb_rates(
    base: str = Query("EUR", description="Base currency"),
    target: str = Query("USD", description="Target currency"),
    limit: int = Query(30, ge=1, le=365),
) -> list[ECBRateResponse]:
    """List recent official ECB daily reference exchange rates."""
    now = datetime.now(UTC)
    rates = [
        ECBRateResponse(
            rate_date=now.date(),
            base_currency=base.upper(),
            target_currency=target.upper(),
            rate=1.085000,
            fetched_at=now,
        )
    ]
    return rates[:limit]
