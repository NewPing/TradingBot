"""Unit tests for Fundamental feature extraction, normalization, and L3 signals."""

from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import (
    BucketId,
    FundamentalSnapshot,
    Order,
    OrderType,
    Quantity,
    Side,
    SignalLayer,
    Symbol,
    TimeInForce,
)
from atlas.risk.blackout import EarningsBlackoutGuard
from atlas.signals.features.fundamental import (
    FundamentalFeatureExtractor,
    SectorRelativeNormalizer,
)
from atlas.signals.l3_fundamental import (
    EarningsSurpriseSignalProvider,
    ValuationQualitySignalProvider,
)
from atlas.strategies.builder import build_signal_provider


def test_fundamental_feature_extractor_metrics() -> None:
    extractor = FundamentalFeatureExtractor()
    snap = FundamentalSnapshot(
        symbol=Symbol("AAPL"),
        report_date=datetime(2026, 6, 30, tzinfo=UTC),
        filing_date=datetime(2026, 7, 28, 20, 0, tzinfo=UTC),
        period="Q3",
        metrics={
            "revenue": 100000.0,
            "net_income": 25000.0,
            "operating_income": 30000.0,
            "ebitda": 35000.0,
            "eps": 2.0,
            "total_assets": 200000.0,
            "operating_cash_flow": 30000.0,
            "free_cash_flow": 25000.0,
            "roic": 0.35,
            "roe": 0.45,
            "pe_ratio": 25.0,
            "ev_to_ebitda": 18.0,
            "fcf_yield": 0.04,
            "debt_to_equity": 0.5,
            "accrual_ratio": -0.025,  # (25k - 30k) / 200k = -0.025
            "gross_margin": 0.45,
            "operating_margin": 0.30,
            "net_margin": 0.25,
        },
    )

    feats = extractor.compute_features_from_snapshot(snap)
    assert feats["fund_roic"] == 0.35
    assert feats["fund_accrual_ratio"] == -0.025
    assert feats["fund_ev_ebitda"] == 18.0
    assert feats["fund_fcf_yield"] == 0.04
    assert 0.0 <= feats["fund_quality_score"] <= 1.0
    assert 0.0 <= feats["fund_value_score"] <= 1.0


def test_sector_relative_normalizer() -> None:
    sym_sec_map = {
        Symbol("AAPL"): "Tech",
        Symbol("MSFT"): "Tech",
        Symbol("JPM"): "Financials",
    }
    normalizer = SectorRelativeNormalizer(sym_sec_map)

    universe_features = {
        Symbol("AAPL"): {
            "fund_roic": 0.50,
            "fund_ev_ebitda": 25.0,
            "fund_fcf_yield": 0.04,
            "fund_quality_score": 0.85,
            "fund_value_score": 0.60,
            "fund_accrual_ratio": -0.02,
        },
        Symbol("MSFT"): {
            "fund_roic": 0.30,
            "fund_ev_ebitda": 30.0,
            "fund_fcf_yield": 0.03,
            "fund_quality_score": 0.75,
            "fund_value_score": 0.50,
            "fund_accrual_ratio": -0.01,
        },
        Symbol("JPM"): {
            "fund_roic": 0.15,
            "fund_ev_ebitda": 10.0,
            "fund_fcf_yield": 0.07,
            "fund_quality_score": 0.60,
            "fund_value_score": 0.80,
            "fund_accrual_ratio": 0.00,
        },
    }

    zscores = normalizer.compute_sector_zscores(universe_features)
    assert Symbol("AAPL") in zscores
    assert Symbol("MSFT") in zscores
    assert Symbol("JPM") in zscores
    # AAPL has higher ROIC than MSFT in Tech sector -> positive z-score
    assert zscores[Symbol("AAPL")]["sector_zscore_roic"] > 0
    assert zscores[Symbol("MSFT")]["sector_zscore_roic"] < 0


def test_l3_valuation_quality_signal_provider() -> None:
    clock = SimClock(datetime(2026, 8, 1, tzinfo=UTC))
    snap = FundamentalSnapshot(
        symbol=Symbol("AAPL"),
        report_date=datetime(2026, 6, 30, tzinfo=UTC),
        filing_date=datetime(2026, 7, 28, 20, 0, tzinfo=UTC),
        period="Q3",
        metrics={
            "roic": 0.40,
            "accrual_ratio": -0.02,
            "fcf_yield": 0.05,
            "ev_to_ebitda": 18.0,
            "gross_margin": 0.45,
            "operating_margin": 0.30,
            "net_margin": 0.25,
            "pe_ratio": 24.0,
            "debt_to_equity": 0.8,
        },
    )

    import polars as pl

    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df=pl.DataFrame(),
        fundamentals_map={Symbol("AAPL"): [snap]},
    )

    provider = ValuationQualitySignalProvider()
    sig = provider.evaluate(ctx, Symbol("AAPL"))

    assert sig is not None
    assert sig.provider == "l3_val_quality"
    assert sig.layer == SignalLayer.L3_FUNDAMENTAL
    assert sig.score > 0.0  # High quality + reasonable value
    assert sig.confidence >= 0.5
    assert "ROIC=" in sig.rationale


def test_l3_earnings_surprise_signal_provider() -> None:
    clock = SimClock(datetime(2026, 8, 1, tzinfo=UTC))
    snap = FundamentalSnapshot(
        symbol=Symbol("NVDA"),
        report_date=datetime(2026, 6, 30, tzinfo=UTC),
        filing_date=datetime(2026, 7, 28, 20, 0, tzinfo=UTC),
        period="Q2",
        metrics={
            "eps_actual": 0.68,
            "eps_estimated": 0.60,
        },
    )

    import polars as pl

    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df=pl.DataFrame(),
        fundamentals_map={Symbol("NVDA"): [snap]},
    )

    provider = EarningsSurpriseSignalProvider()
    sig = provider.evaluate(ctx, Symbol("NVDA"))

    assert sig is not None
    assert sig.provider == "l3_earnings_surprise"
    assert sig.layer == SignalLayer.L3_FUNDAMENTAL
    assert sig.score > 0.0  # Positive surprise
    assert "Standardized EPS surprise" in sig.rationale


def test_earnings_blackout_guard() -> None:
    now_dt = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
    clock = SimClock(now_dt)

    earnings_event_date = datetime(2026, 8, 21, 20, 0, tzinfo=UTC)  # Tomorrow (within 2d)

    import polars as pl

    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df=pl.DataFrame(),
        earnings_calendar_map={Symbol("NVDA"): [earnings_event_date]},
    )

    guard = EarningsBlackoutGuard(
        blackout_days_pre=2, protected_buckets=[BucketId.MOONSHOT, BucketId.SWING]
    )

    # 1. New entry in MOONSHOT bucket during blackout -> blocked
    buy_order = Order(
        id="ord_1",
        run_id="run_1",
        strategy_version_id="ver_1",
        bucket=BucketId.MOONSHOT,
        symbol=Symbol("NVDA"),
        side=Side.BUY,
        qty=Quantity(100),
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=now_dt,
    )
    res = guard.validate_order(buy_order, ctx)
    assert not res.passed
    assert res.rule_name == "EARNINGS_BLACKOUT_ACTIVE"

    # 2. Sell/exit in MOONSHOT bucket during blackout -> allowed
    sell_order = Order(
        id="ord_2",
        run_id="run_1",
        strategy_version_id="ver_1",
        bucket=BucketId.MOONSHOT,
        symbol=Symbol("NVDA"),
        side=Side.SELL,
        qty=Quantity(100),
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=now_dt,
    )
    res_sell = guard.validate_order(sell_order, ctx)
    assert res_sell.passed

    # 3. Buy order in CORE bucket (unprotected) -> allowed
    core_buy = Order(
        id="ord_3",
        run_id="run_1",
        strategy_version_id="ver_1",
        bucket=BucketId.CORE,
        symbol=Symbol("NVDA"),
        side=Side.BUY,
        qty=Quantity(100),
        type=OrderType.MARKET,
        tif=TimeInForce.DAY,
        created_ts=now_dt,
    )
    res_core = guard.validate_order(core_buy, ctx)
    assert res_core.passed


def test_strategy_builder_l3_providers() -> None:
    p1 = build_signal_provider("l3_val_quality", {"min_roic": 0.10, "max_accrual_ratio": 0.04})
    assert isinstance(p1, ValuationQualitySignalProvider)
    assert p1.min_roic == 0.10

    p2 = build_signal_provider("l3_earnings_surprise", {"lookback_days": 45})
    assert isinstance(p2, EarningsSurpriseSignalProvider)
    assert p2.lookback_days == 45
