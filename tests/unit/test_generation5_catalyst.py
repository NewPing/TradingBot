"""Unit test and verification for Generation 5: The Executive & Catalyst Alpha Strategy (core_catalyst_ai_v5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import (
    BucketId,
    NewsItem,
    SignalLayer,
    Symbol,
)
from atlas.signals.l4_narrative import (
    ExecutiveCatalystSignalProvider,
    MacroGeopoliticalShockSignalProvider,
)
from atlas.strategies.builder import build_aggregator, build_position_policy, build_signal_provider
from atlas.strategies.spec import StrategySpec


def test_core_catalyst_ai_v5_spec_parsing() -> None:
    spec_path = Path("strategies/core_catalyst_ai_v5.yaml")
    assert spec_path.exists()

    spec = StrategySpec.from_yaml(spec_path.read_text(encoding="utf-8"))
    assert spec.name == "core_catalyst_ai_v5"
    assert spec.version == "5.0.0"
    assert spec.family == "core_trend"
    assert len(spec.signals) == 8

    # Build all signal providers
    providers = [build_signal_provider(sig.provider, sig.params) for sig in spec.signals]
    assert len(providers) == 8

    # Build aggregator and position policy
    agg = build_aggregator(spec)
    assert agg.min_confidence == 0.40

    policy = build_position_policy(spec)
    assert policy.bucket == BucketId.CORE


def test_executive_catalyst_signal_provider_evaluation() -> None:
    provider = ExecutiveCatalystSignalProvider(
        id="l4_executive_catalyst",
        lookback_hours=72,
        catalyst_weight=1.5,
        min_relevance=0.4,
    )
    now = datetime(2026, 8, 24, 16, 0, tzinfo=UTC)
    clock = SimClock(now)

    # Mock historical market context with high-impact executive news
    articles = [
        NewsItem(
            id="news_1",
            ts=now - timedelta(hours=6),
            source="Alpaca",
            symbols=(Symbol("NVDA"),),
            title="Jensen Huang announces next-generation AI GPU architecture with 5x throughput",
            body="CEO keynote reveals breakthrough datacenter silicon.",
            url="https://news.example.com/nvda",
            sentiment_score=0.90,
            relevance_score=0.98,
            novelty_score=0.90,
            impact="LONG",
            confidence=0.95,
            rationale="Major GPU generation launch drives massive multi-year datacenter upgrade cycle.",
        )
    ]
    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df={Symbol("NVDA"): pl.DataFrame()},
        news_map={Symbol("NVDA"): articles},
    )

    signal = provider.evaluate(ctx, Symbol("NVDA"))
    assert signal is not None
    assert signal.layer == SignalLayer.L4_NARRATIVE
    assert signal.score > 0.80
    assert signal.confidence >= 0.60
    assert "Executive & Catalyst" in signal.rationale
    assert (
        "GPU" in signal.rationale or "datacenter" in signal.rationale or "cycle" in signal.rationale
    )


def test_macro_geopolitical_shock_signal_provider() -> None:
    provider = MacroGeopoliticalShockSignalProvider(
        id="l4_macro_shock",
        lookback_hours=48,
        tariff_sensitivity=1.2,
    )
    now = datetime(2026, 8, 24, 16, 0, tzinfo=UTC)
    clock = SimClock(now)

    macro_news = [
        NewsItem(
            id="news_trump_tariff",
            ts=now - timedelta(hours=4),
            source="Alpaca",
            symbols=(Symbol("SPY"),),
            title="New 25% tariff announced on imported steel and semiconductors",
            body="Executive order imposes broad retaliatory tariffs on component imports.",
            url="https://news.example.com/macro",
            sentiment_score=-0.75,
            relevance_score=0.95,
            novelty_score=0.85,
            impact="MEDIUM",
            confidence=0.90,
            rationale="Tariff shock disrupts supply chains and increases component costs.",
        )
    ]
    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df={Symbol("SPY"): pl.DataFrame(), Symbol("TSLA"): pl.DataFrame()},
        news_map={Symbol("SPY"): macro_news},
    )

    signal = provider.evaluate(ctx, Symbol("TSLA"))
    assert signal is not None
    assert signal.score < -0.50  # Bearish macro shock warning
    assert signal.confidence >= 0.60
    assert "Macro/Geopolitical Shock" in signal.rationale
