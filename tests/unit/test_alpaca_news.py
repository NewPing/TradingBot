"""Unit tests for Alpaca News data provider and content hashing."""

from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.types import Symbol
from atlas.data.providers.alpaca_news import AlpacaNewsProvider


def test_alpaca_news_hashing_and_normalization() -> None:
    provider = AlpacaNewsProvider(api_key_id="test_key", api_secret="test_secret")

    raw_article = {
        "id": 987654,
        "headline": "NVIDIA Reports Record Q3 Revenue",
        "summary": "Accelerated computing revenue up 112% year over year.",
        "content": "<p>NVIDIA announced record revenue driven by data center demand.</p>",
        "created_at": "2026-08-20T14:30:00Z",
        "url": "https://data.alpaca.markets/news/987654",
        "symbols": ["NVDA", "AAPL"],
        "source": "BenZinga",
    }

    norm = provider.normalize_article(raw_article)

    assert norm["id"] == "alpaca_987654"
    assert norm["source"] == "BenZinga"
    assert norm["title"] == "NVIDIA Reports Record Q3 Revenue"
    assert norm["symbols"] == [Symbol("NVDA"), Symbol("AAPL")]
    assert norm["published_at"] == datetime(2026, 8, 20, 14, 30, tzinfo=UTC)
    assert len(norm["content_hash"]) == 64  # SHA-256


def test_alpaca_news_deduplication_hash_deterministic() -> None:
    url = "https://example.com/news/1"
    title = "Market rallies on rate cut expectations"
    summary = "Federal Reserve signals policy easing."

    hash1 = AlpacaNewsProvider.compute_content_hash(url, title, summary)
    hash2 = AlpacaNewsProvider.compute_content_hash(url, title, summary)

    assert hash1 == hash2

    hash3 = AlpacaNewsProvider.compute_content_hash(url, title, summary + " extra")
    assert hash1 != hash3
