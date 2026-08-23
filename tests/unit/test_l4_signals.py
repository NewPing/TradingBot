"""Unit tests for L4 Narrative & LLM Signal Providers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import NewsItem, SignalLayer, Symbol
from atlas.signals.l4_narrative import (
    NarrativeMomentumSignalProvider,
    NewsSentimentSignalProvider,
)


def test_news_sentiment_signal_provider() -> None:
    t0 = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    clock = SimClock(t0)

    bars_df = pl.DataFrame(
        {
            "symbol": ["NVDA"],
            "ts": [t0],
            "open": [Decimal("120.0")],
            "high": [Decimal("122.0")],
            "low": [Decimal("119.0")],
            "close": [Decimal("121.0")],
            "volume": [5000000],
        }
    )

    art1 = NewsItem(
        id="nvda_1",
        ts=t0 - timedelta(hours=3),
        source="alpaca_news",
        symbols=(Symbol("NVDA"),),
        title="NVIDIA strong growth",
        body="...",
        url="...",
        sentiment_score=0.8,
        relevance_score=0.9,
        novelty_score=0.7,
        confidence=0.85,
        rationale="Strong Blackwell datacenter ramp.",
    )

    news_map = {Symbol("NVDA"): [art1]}
    ctx = HistoricalMarketContext(clock=clock, bars_df=bars_df, news_map=news_map)

    provider = NewsSentimentSignalProvider()
    assert provider.layer == SignalLayer.L4_NARRATIVE

    sig = provider.evaluate(ctx, Symbol("NVDA"))
    assert sig is not None
    assert sig.score > 0.5
    assert sig.confidence >= 0.5
    assert "Blackwell" in sig.rationale


def test_narrative_momentum_signal_provider() -> None:
    t0 = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    clock = SimClock(t0)

    bars_df = pl.DataFrame(
        {
            "symbol": ["AAPL"],
            "ts": [t0],
            "open": [Decimal("200.0")],
            "high": [Decimal("202.0")],
            "low": [Decimal("199.0")],
            "close": [Decimal("201.0")],
            "volume": [3000000],
        }
    )

    # Fast news item (recent 6h, very positive)
    art_fast = NewsItem(
        id="aapl_fast",
        ts=t0 - timedelta(hours=6),
        source="alpaca_news",
        symbols=(Symbol("AAPL"),),
        title="Apple services beat",
        body="...",
        url="...",
        sentiment_score=0.9,
        relevance_score=0.9,
    )

    # Slow news item (48h ago, mildly positive)
    art_slow = NewsItem(
        id="aapl_slow",
        ts=t0 - timedelta(hours=48),
        source="alpaca_news",
        symbols=(Symbol("AAPL"),),
        title="Apple quarterly preview",
        body="...",
        url="...",
        sentiment_score=0.2,
        relevance_score=0.8,
    )

    news_map = {Symbol("AAPL"): [art_fast, art_slow]}
    ctx = HistoricalMarketContext(clock=clock, bars_df=bars_df, news_map=news_map)

    provider = NarrativeMomentumSignalProvider()
    sig = provider.evaluate(ctx, Symbol("AAPL"))

    assert sig is not None
    assert sig.score > 0.0
    assert "Narrative Momentum" in sig.rationale
