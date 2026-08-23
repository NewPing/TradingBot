"""Comprehensive unit tests for base, tiingo, alpaca, and yfinance providers."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from atlas.core.types import Symbol
from atlas.data.providers.alpaca import AlpacaMarketDataProvider
from atlas.data.providers.base import (
    AuthenticationError,
    BaseDataProvider,
    ResourceNotFoundError,
    TokenBucketLimiter,
)
from atlas.data.providers.tiingo import TiingoProvider
from atlas.data.providers.yfinance import YFinanceProvider


class DummyProvider(BaseDataProvider):
    async def fetch_daily_bars(
        self, symbol: Symbol, start_date: date, end_date: date
    ) -> list[dict]:
        _ = (symbol, start_date, end_date)
        return []

    async def fetch_corporate_actions(
        self, symbol: Symbol, start_date: date, end_date: date
    ) -> list[dict]:
        _ = (symbol, start_date, end_date)
        return []

    async def is_healthy(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_token_bucket_limiter() -> None:
    limiter = TokenBucketLimiter(rate_per_sec=100.0, capacity=10.0)
    await limiter.acquire(1.0)
    assert limiter.tokens < 10.0


@pytest.mark.asyncio
async def test_base_provider_caching(tmp_path) -> None:
    provider = DummyProvider(name="test", cache_dir=tmp_path)
    provider._write_cache("key1", {"foo": "bar"})
    cached = provider._read_cache("key1")
    assert cached == {"foo": "bar"}
    assert provider._read_cache("non_existent") is None


@pytest.mark.asyncio
async def test_base_provider_request_success() -> None:
    provider = DummyProvider(name="test")
    client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}
    client.request.return_value = mock_resp

    data = await provider._request_with_retry(client, "GET", "https://example.com")
    assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_base_provider_404_error() -> None:
    provider = DummyProvider(name="test")
    client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    client.request.return_value = mock_resp

    with pytest.raises(ResourceNotFoundError):
        await provider._request_with_retry(client, "GET", "https://example.com/notfound")


@pytest.mark.asyncio
async def test_base_provider_401_auth_error() -> None:
    provider = DummyProvider(name="test")
    client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    client.request.return_value = mock_resp

    with pytest.raises(AuthenticationError):
        await provider._request_with_retry(client, "GET", "https://example.com/auth")


@pytest.mark.asyncio
async def test_tiingo_provider_fetch_daily_bars() -> None:
    provider = TiingoProvider(api_key="test_token")
    mock_response = [
        {
            "date": "2023-01-03T00:00:00.000Z",
            "close": 125.07,
            "high": 130.9,
            "low": 124.17,
            "open": 130.28,
            "volume": 112117500,
            "adjClose": 124.3,
            "adjHigh": 130.1,
            "adjLow": 123.4,
            "adjOpen": 129.5,
            "adjVolume": 112117500,
            "divCash": 0.0,
            "splitFactor": 1.0,
        }
    ]

    with patch.object(provider, "_request_with_retry", new=AsyncMock(return_value=mock_response)):
        bars = await provider.fetch_daily_bars(Symbol("AAPL"), date(2023, 1, 1), date(2023, 1, 5))
        assert len(bars) == 1
        assert bars[0]["close"] == 125.07


@pytest.mark.asyncio
async def test_tiingo_provider_metadata_and_health() -> None:
    provider = TiingoProvider(api_key="test_token")
    with patch.object(
        provider,
        "_request_with_retry",
        new=AsyncMock(return_value={"ticker": "AAPL", "name": "Apple"}),
    ):
        meta = await provider.fetch_ticker_metadata(Symbol("AAPL"))
        assert meta["ticker"] == "AAPL"
        healthy = await provider.is_healthy()
        assert healthy is True


@pytest.mark.asyncio
async def test_alpaca_provider_health_and_actions() -> None:
    provider = AlpacaMarketDataProvider(api_key_id="key", api_secret="secret")
    with patch.object(
        provider, "_request_with_retry", new=AsyncMock(return_value={"bars": [{"c": 100}]})
    ):
        healthy = await provider.is_healthy()
        assert healthy is True

    with patch.object(provider, "_request_with_retry", new=AsyncMock(return_value=[{"id": "ca1"}])):
        actions = await provider.fetch_corporate_actions(
            Symbol("AAPL"), date(2023, 1, 1), date(2023, 1, 5)
        )
        assert len(actions) == 1


@pytest.mark.asyncio
async def test_yfinance_provider_corporate_actions() -> None:
    provider = YFinanceProvider()
    mock_bars = [
        {
            "date": "2023-01-03",
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 103.0,
            "volume": 1000000,
            "adj_close": 102.5,
            "dividends": 0.50,
            "stock_splits": 2.0,
        }
    ]
    with patch.object(provider, "fetch_daily_bars", new=AsyncMock(return_value=mock_bars)):
        actions = await provider.fetch_corporate_actions(
            Symbol("SPY"), date(2023, 1, 1), date(2023, 1, 5)
        )
        assert len(actions) == 2
