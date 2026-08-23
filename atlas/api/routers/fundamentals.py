"""FastAPI router for Fundamentals, Valuation Multiples, and Earnings Calendar."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query

from atlas.api.schemas.fundamentals import (
    EarningsEventResponse,
    FundamentalScreenerItem,
    FundamentalScreenerResponse,
    FundamentalSnapshotResponse,
)
from atlas.core.types import FundamentalSnapshot, Symbol
from atlas.signals.features.fundamental import (
    FundamentalFeatureExtractor,
    SectorRelativeNormalizer,
)

router = APIRouter(prefix="/api/v1/fundamentals", tags=["Fundamentals & Valuation"])

# Pre-populated realistic baseline metrics for representative universe symbols
SAMPLE_FUNDAMENTALS: dict[str, dict[str, Any]] = {
    "AAPL": {
        "sector": "Technology",
        "report_date": "2026-06-30",
        "filing_date": "2026-07-28T20:30:00Z",
        "period": "Q3",
        "metrics": {
            "revenue": 94800000000.0,
            "net_income": 23600000000.0,
            "operating_income": 28500000000.0,
            "ebitda": 31000000000.0,
            "eps": 1.53,
            "total_assets": 352500000000.0,
            "operating_cash_flow": 28200000000.0,
            "free_cash_flow": 25100000000.0,
            "roic": 0.54,
            "roe": 1.45,
            "pe_ratio": 29.5,
            "ev_to_ebitda": 22.1,
            "fcf_yield": 0.038,
            "debt_to_equity": 1.42,
            "accrual_ratio": -0.013,
            "gross_margin": 0.462,
            "operating_margin": 0.301,
            "net_margin": 0.249,
            "revenue_growth_yoy": 0.082,
            "eps_growth_yoy": 0.114,
        },
    },
    "MSFT": {
        "sector": "Technology",
        "report_date": "2026-06-30",
        "filing_date": "2026-07-25T21:00:00Z",
        "period": "Q4",
        "metrics": {
            "revenue": 64700000000.0,
            "net_income": 22000000000.0,
            "operating_income": 27900000000.0,
            "ebitda": 33100000000.0,
            "eps": 2.95,
            "total_assets": 512000000000.0,
            "operating_cash_flow": 37200000000.0,
            "free_cash_flow": 23300000000.0,
            "roic": 0.31,
            "roe": 0.38,
            "pe_ratio": 33.2,
            "ev_to_ebitda": 24.8,
            "fcf_yield": 0.032,
            "debt_to_equity": 0.41,
            "accrual_ratio": -0.029,
            "gross_margin": 0.697,
            "operating_margin": 0.431,
            "net_margin": 0.340,
            "revenue_growth_yoy": 0.151,
            "eps_growth_yoy": 0.178,
        },
    },
    "NVDA": {
        "sector": "Technology",
        "report_date": "2026-07-31",
        "filing_date": "2026-08-20T20:15:00Z",
        "period": "Q2",
        "metrics": {
            "revenue": 30000000000.0,
            "net_income": 16600000000.0,
            "operating_income": 18600000000.0,
            "ebitda": 19500000000.0,
            "eps": 0.68,
            "total_assets": 85000000000.0,
            "operating_cash_flow": 14500000000.0,
            "free_cash_flow": 13500000000.0,
            "roic": 0.72,
            "roe": 0.95,
            "pe_ratio": 42.0,
            "ev_to_ebitda": 32.5,
            "fcf_yield": 0.024,
            "debt_to_equity": 0.18,
            "accrual_ratio": 0.024,
            "gross_margin": 0.751,
            "operating_margin": 0.620,
            "net_margin": 0.553,
            "revenue_growth_yoy": 1.22,
            "eps_growth_yoy": 1.52,
        },
    },
    "GOOGL": {
        "sector": "Communication Services",
        "report_date": "2026-06-30",
        "filing_date": "2026-07-23T20:00:00Z",
        "period": "Q2",
        "metrics": {
            "revenue": 84700000000.0,
            "net_income": 23600000000.0,
            "operating_income": 27400000000.0,
            "ebitda": 31200000000.0,
            "eps": 1.89,
            "total_assets": 420000000000.0,
            "operating_cash_flow": 26600000000.0,
            "free_cash_flow": 13400000000.0,
            "roic": 0.28,
            "roe": 0.31,
            "pe_ratio": 23.4,
            "ev_to_ebitda": 16.2,
            "fcf_yield": 0.045,
            "debt_to_equity": 0.10,
            "accrual_ratio": -0.007,
            "gross_margin": 0.582,
            "operating_margin": 0.324,
            "net_margin": 0.279,
            "revenue_growth_yoy": 0.136,
            "eps_growth_yoy": 0.312,
        },
    },
    "AMZN": {
        "sector": "Consumer Cyclical",
        "report_date": "2026-06-30",
        "filing_date": "2026-08-01T20:30:00Z",
        "period": "Q2",
        "metrics": {
            "revenue": 148000000000.0,
            "net_income": 13500000000.0,
            "operating_income": 14700000000.0,
            "ebitda": 28000000000.0,
            "eps": 1.26,
            "total_assets": 550000000000.0,
            "operating_cash_flow": 25300000000.0,
            "free_cash_flow": 17800000000.0,
            "roic": 0.14,
            "roe": 0.22,
            "pe_ratio": 38.5,
            "ev_to_ebitda": 19.5,
            "fcf_yield": 0.036,
            "debt_to_equity": 0.62,
            "accrual_ratio": -0.021,
            "gross_margin": 0.491,
            "operating_margin": 0.099,
            "net_margin": 0.091,
            "revenue_growth_yoy": 0.102,
            "eps_growth_yoy": 0.938,
        },
    },
    "JPM": {
        "sector": "Financial Services",
        "report_date": "2026-06-30",
        "filing_date": "2026-07-12T11:00:00Z",
        "period": "Q2",
        "metrics": {
            "revenue": 50900000000.0,
            "net_income": 18100000000.0,
            "operating_income": 21000000000.0,
            "ebitda": 21500000000.0,
            "eps": 6.12,
            "total_assets": 4150000000000.0,
            "operating_cash_flow": 19500000000.0,
            "free_cash_flow": 18200000000.0,
            "roic": 0.16,
            "roe": 0.19,
            "pe_ratio": 12.1,
            "ev_to_ebitda": 9.5,
            "fcf_yield": 0.071,
            "debt_to_equity": 1.85,
            "accrual_ratio": -0.0003,
            "gross_margin": 0.900,
            "operating_margin": 0.412,
            "net_margin": 0.355,
            "revenue_growth_yoy": 0.201,
            "eps_growth_yoy": 0.250,
        },
    },
}

SAMPLE_EARNINGS: list[dict[str, Any]] = [
    {
        "symbol": "NVDA",
        "event_date": "2026-08-27",
        "time_of_day": "AMC",
        "fiscal_period": "Q2-2026",
        "eps_estimated": 0.64,
        "eps_actual": None,
        "revenue_estimated": 28700000000.0,
        "revenue_actual": None,
    },
    {
        "symbol": "CRWD",
        "event_date": "2026-08-28",
        "time_of_day": "AMC",
        "fiscal_period": "Q2-2026",
        "eps_estimated": 0.81,
        "eps_actual": None,
        "revenue_estimated": 958000000.0,
        "revenue_actual": None,
    },
    {
        "symbol": "AAPL",
        "event_date": "2026-10-29",
        "time_of_day": "AMC",
        "fiscal_period": "Q4-2026",
        "eps_estimated": 1.62,
        "eps_actual": None,
        "revenue_estimated": 98500000000.0,
        "revenue_actual": None,
    },
    {
        "symbol": "MSFT",
        "event_date": "2026-10-22",
        "time_of_day": "AMC",
        "fiscal_period": "Q1-2027",
        "eps_estimated": 3.10,
        "eps_actual": None,
        "revenue_estimated": 68000000000.0,
        "revenue_actual": None,
    },
]


@router.get("/{symbol}", response_model=FundamentalSnapshotResponse)
def get_symbol_fundamentals(symbol: str) -> FundamentalSnapshotResponse:
    """Get latest point-in-time fundamental filing and valuation scorecard for symbol."""
    sym = symbol.upper()
    data = SAMPLE_FUNDAMENTALS.get(sym)
    if not data:
        # Generate default fallback
        data = {
            "sector": "General",
            "report_date": "2026-06-30",
            "filing_date": "2026-07-31T20:00:00Z",
            "period": "Q2",
            "metrics": {
                "roic": 0.12,
                "pe_ratio": 20.0,
                "ev_to_ebitda": 14.0,
                "fcf_yield": 0.04,
                "debt_to_equity": 0.50,
                "accrual_ratio": -0.01,
                "gross_margin": 0.45,
                "operating_margin": 0.18,
            },
        }

    rep_dt = datetime.fromisoformat(data["report_date"]).replace(tzinfo=UTC)
    filing_dt = datetime.fromisoformat(data["filing_date"].replace("Z", "+00:00"))

    snap = FundamentalSnapshot(
        symbol=Symbol(sym),
        report_date=rep_dt,
        filing_date=filing_dt,
        period=str(data["period"]),
        metrics=data["metrics"],
    )

    extractor = FundamentalFeatureExtractor()
    feats = extractor.compute_features_from_snapshot(snap)

    rationale = (
        f"{sym} Quality Score: {feats['fund_quality_score'] * 100:.0f}/100 | "
        f"Value Score: {feats['fund_value_score'] * 100:.0f}/100 | "
        f"ROIC: {feats['fund_roic'] * 100:.1f}% | "
        f"Sloan Accruals: {feats['fund_accrual_ratio']:.3f} | "
        f"FCF Yield: {feats['fund_fcf_yield'] * 100:.1f}%"
    )

    return FundamentalSnapshotResponse(
        symbol=sym,
        report_date=data["report_date"],
        filing_date=data["filing_date"],
        period=str(data["period"]),
        metrics=data["metrics"],
        quality_score=feats["fund_quality_score"],
        value_score=feats["fund_value_score"],
        roic=feats["fund_roic"],
        fcf_yield=feats["fund_fcf_yield"],
        sloan_accrual=feats["fund_accrual_ratio"],
        ev_ebitda=feats["fund_ev_ebitda"],
        pe_ratio=feats["fund_pe_ratio"],
        debt_to_equity=feats["fund_debt_to_equity"],
        gross_margin=feats["fund_gross_margin"],
        operating_margin=feats["fund_operating_margin"],
        rationale=rationale,
    )


@router.get("/earnings/calendar", response_model=list[EarningsEventResponse])
def get_earnings_calendar(
    blackout_days_pre: Annotated[
        int, Query(description="Pre-earnings blackout window in days")
    ] = 2,
) -> list[EarningsEventResponse]:
    """Get earnings calendar events with active blackout window indicators."""
    today = date(2026, 8, 23)
    results: list[EarningsEventResponse] = []

    for ev in SAMPLE_EARNINGS:
        ev_date = date.fromisoformat(ev["event_date"])
        diff_days = (ev_date - today).days

        if diff_days < 0:
            status_val = "PAST"
        elif 0 <= diff_days <= blackout_days_pre:
            status_val = "BLACKOUT_ACTIVE"
        else:
            status_val = "SAFE"

        results.append(
            EarningsEventResponse(
                symbol=ev["symbol"],
                event_date=ev["event_date"],
                time_of_day=ev["time_of_day"],
                fiscal_period=ev.get("fiscal_period"),
                eps_estimated=ev.get("eps_estimated"),
                eps_actual=ev.get("eps_actual"),
                revenue_estimated=ev.get("revenue_estimated"),
                revenue_actual=ev.get("revenue_actual"),
                blackout_status=status_val,
                days_until_event=diff_days,
            )
        )

    # Sort upcoming first
    results.sort(key=lambda x: x.days_until_event)
    return results


@router.get("/screener/universe", response_model=FundamentalScreenerResponse)
def get_fundamental_screener() -> FundamentalScreenerResponse:
    """Get ranked universe cross-sectional fundamental and valuation metrics."""
    extractor = FundamentalFeatureExtractor()
    sym_sec_map = {Symbol(sym): data["sector"] for sym, data in SAMPLE_FUNDAMENTALS.items()}
    normalizer = SectorRelativeNormalizer(sym_sec_map)

    feats_by_sym: dict[Symbol, dict[str, float]] = {}
    items: list[FundamentalScreenerItem] = []

    for sym_str, data in SAMPLE_FUNDAMENTALS.items():
        sym = Symbol(sym_str)
        rep_dt = datetime.fromisoformat(data["report_date"]).replace(tzinfo=UTC)
        filing_dt = datetime.fromisoformat(data["filing_date"].replace("Z", "+00:00"))
        snap = FundamentalSnapshot(
            symbol=sym,
            report_date=rep_dt,
            filing_date=filing_dt,
            period=str(data["period"]),
            metrics=data["metrics"],
        )
        feats = extractor.compute_features_from_snapshot(snap)
        feats_by_sym[sym] = feats

    sector_zscores = normalizer.compute_sector_zscores(feats_by_sym)

    for sym_str, data in SAMPLE_FUNDAMENTALS.items():
        sym = Symbol(sym_str)
        f = feats_by_sym[sym]
        z = sector_zscores.get(sym, {})
        items.append(
            FundamentalScreenerItem(
                symbol=sym_str,
                sector=data["sector"],
                quality_score=f["fund_quality_score"],
                value_score=f["fund_value_score"],
                roic=f["fund_roic"],
                fcf_yield=f["fund_fcf_yield"],
                sloan_accrual=f["fund_accrual_ratio"],
                ev_ebitda=f["fund_ev_ebitda"],
                pe_ratio=f["fund_pe_ratio"],
                sector_zscore_quality=z.get("sector_zscore_quality_score", 0.0),
                sector_zscore_value=z.get("sector_zscore_value_score", 0.0),
            )
        )

    # Sort descending by quality score
    items.sort(key=lambda x: x.quality_score, reverse=True)
    return FundamentalScreenerResponse(total=len(items), items=items)
