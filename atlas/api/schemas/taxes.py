"""Pydantic schemas for German tax reporting and FIFO lot management (Phase 9)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class TaxLotResponse(BaseModel):
    id: str
    symbol: str
    asset_category: str
    buy_date: date
    buy_ts: datetime
    quantity_initial: int
    quantity_remaining: int
    buy_price_usd: float
    buy_fx_rate_eur_usd: float
    buy_price_eur: float
    total_cost_eur: float
    commission_eur: float
    status: str
    closed_at: datetime | None = None


class TaxEventResponse(BaseModel):
    id: str
    tax_lot_id: str
    symbol: str
    asset_category: str
    tax_year: int
    sell_date: date
    sell_ts: datetime
    quantity: int
    buy_price_eur: float
    sell_price_usd: float
    sell_fx_rate_eur_usd: float
    sell_price_eur: float
    proceeds_eur: float
    cost_basis_eur: float
    commission_eur: float
    gain_loss_eur: float
    is_gain: bool
    kest_amount_eur: float
    soli_amount_eur: float
    kirchensteuer_eur: float
    total_tax_eur: float


class AnnualTaxReportResponse(BaseModel):
    tax_year: int
    total_realized_gains_eur: float
    total_realized_losses_eur: float
    net_taxable_income_eur: float
    aktien_gains_eur: float
    aktien_losses_eur: float
    aktien_loss_carryforward_eur: float
    sonstige_gains_eur: float
    sonstige_losses_eur: float
    sonstige_loss_carryforward_eur: float
    sparerpauschbetrag_used_eur: float
    sparerpauschbetrag_remaining_eur: float
    total_kest_eur: float
    total_soli_eur: float
    total_kirchensteuer_eur: float
    total_tax_liability_eur: float
    effective_tax_rate_pct: float
    total_trades_processed: int
    open_lots_count: int
    open_lots_cost_basis_eur: float


class ECBRateResponse(BaseModel):
    rate_date: date
    base_currency: str
    target_currency: str
    rate: float
    fetched_at: datetime
