"""Property-based tests for fundamental quality and valuation metrics using Hypothesis."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from atlas.core.types import FundamentalSnapshot, Symbol
from atlas.signals.features.fundamental import (
    FundamentalFeatureExtractor,
    SectorRelativeNormalizer,
)


@given(
    net_income=st.floats(min_value=-1e10, max_value=1e10, allow_nan=False),
    operating_cash_flow=st.floats(min_value=-1e10, max_value=1e10, allow_nan=False),
    total_assets=st.floats(min_value=1.0, max_value=1e11, allow_nan=False),
    roic=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False),
    ev_to_ebitda=st.floats(min_value=0.1, max_value=100.0, allow_nan=False),
    fcf_yield=st.floats(min_value=-0.5, max_value=0.5, allow_nan=False),
)
@settings(max_examples=100)
def test_fundamental_feature_extractor_bounds(
    net_income: float,
    operating_cash_flow: float,
    total_assets: float,
    roic: float,
    ev_to_ebitda: float,
    fcf_yield: float,
) -> None:
    extractor = FundamentalFeatureExtractor()
    snap = FundamentalSnapshot(
        symbol=Symbol("TEST"),
        report_date=datetime(2026, 6, 30, tzinfo=UTC),
        filing_date=datetime(2026, 7, 28, tzinfo=UTC),
        period="Q2",
        metrics={
            "net_income": net_income,
            "operating_cash_flow": operating_cash_flow,
            "total_assets": total_assets,
            "roic": roic,
            "ev_to_ebitda": ev_to_ebitda,
            "fcf_yield": fcf_yield,
        },
    )

    feats = extractor.compute_features_from_snapshot(snap)

    # Sloan accrual ratio: (NI - CFO) / Total Assets
    expected_accrual = (net_income - operating_cash_flow) / total_assets
    assert abs(feats["fund_accrual_ratio"] - expected_accrual) < 1e-5

    # Quality and value scores are always strictly bounded [0.0, 1.0]
    assert 0.0 <= feats["fund_quality_score"] <= 1.0
    assert 0.0 <= feats["fund_value_score"] <= 1.0


@given(
    roic_values=st.lists(
        st.floats(min_value=-0.5, max_value=1.5, allow_nan=False),
        min_size=2,
        max_size=10,
    )
)
@settings(max_examples=50)
def test_sector_normalizer_zscore_bounds(roic_values: list[float]) -> None:
    symbols = [Symbol(f"SYM_{i}") for i in range(len(roic_values))]
    sym_sec_map = dict.fromkeys(symbols, "Tech")
    normalizer = SectorRelativeNormalizer(sym_sec_map)

    universe_features = {sym: {"fund_roic": roic_values[i]} for i, sym in enumerate(symbols)}

    zscores = normalizer.compute_sector_zscores(
        universe_features, metrics_to_normalize=["fund_roic"]
    )
    for sym in symbols:
        z = zscores[sym]["sector_zscore_roic"]
        # Z-scores are clamped to [-3.0, 3.0]
        assert -3.0 <= z <= 3.0
