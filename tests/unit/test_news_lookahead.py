"""Lookahead prevention verification for news queries in MarketContext."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import polars as pl

from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import NewsItem, Symbol


def test_market_context_news_zero_lookahead() -> None:
    t0 = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    clock = SimClock(t0)

    bars_df = pl.DataFrame(
        {
            "symbol": ["SPY"],
            "ts": [t0],
            "open": [Decimal("500.0")],
            "high": [Decimal("505.0")],
            "low": [Decimal("495.0")],
            "close": [Decimal("502.0")],
            "volume": [1000000],
        }
    )

    article_past = NewsItem(
        id="past_1",
        ts=t0 - timedelta(hours=2),
        source="alpaca_news",
        symbols=(Symbol("NVDA"),),
        title="NVIDIA past article",
        body="...",
        url="...",
        sentiment_score=0.5,
    )

    article_future = NewsItem(
        id="future_1",
        ts=t0 + timedelta(hours=1),  # Published in the FUTURE relative to clock
        source="alpaca_news",
        symbols=(Symbol("NVDA"),),
        title="NVIDIA future article",
        body="...",
        url="...",
        sentiment_score=0.9,
    )

    news_map = {
        Symbol("NVDA"): [article_past, article_future],
    }

    ctx = HistoricalMarketContext(
        clock=clock,
        bars_df=bars_df,
        news_map=news_map,
    )

    # Query at t0: should only see past article
    items = ctx.news(Symbol("NVDA"), lookback_hours=24)
    assert len(items) == 1
    assert items[0].id == "past_1"

    # Advance clock past future article publication
    clock.set(t0 + timedelta(hours=2))
    items_advanced = ctx.news(Symbol("NVDA"), lookback_hours=24)
    assert len(items_advanced) == 2
    assert [it.id for it in items_advanced] == ["future_1", "past_1"]
