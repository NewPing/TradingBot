"""Unit tests for versioned prompt registry, structured schema validation, and LLM client."""

from __future__ import annotations

import pytest

from atlas.llm.client import LLMClient
from atlas.llm.prompts import LLMNewsAnalysis, PromptRegistry


def test_prompt_registry_hashing() -> None:
    reg = PromptRegistry()
    prompt = reg.get("news_sentiment", "v1.0")

    assert prompt.name == "news_sentiment"
    assert prompt.version == "v1.0"
    assert len(prompt.prompt_hash) == 64
    assert "sentiment" in prompt.schema_json


def test_structured_json_schema_validation() -> None:
    valid_payload = {
        "sentiment": 0.75,
        "relevance": 0.90,
        "horizon": "SHORT_TERM",
        "novelty": 0.80,
        "impact": "BULLISH",
        "confidence": 0.85,
        "rationale": "High datacenter demand drives earnings beat.",
    }

    analysis = LLMNewsAnalysis.model_validate(valid_payload)
    assert analysis.sentiment == 0.75
    assert analysis.impact == "BULLISH"
    assert analysis.horizon == "SHORT_TERM"

    with pytest.raises(ValueError):
        # Out of range sentiment
        LLMNewsAnalysis.model_validate({**valid_payload, "sentiment": 2.5})


@pytest.mark.asyncio
async def test_llm_client_fallback_heuristic() -> None:
    client = LLMClient(base_url="http://127.0.0.1:9999/v1", timeout=0.1)

    analysis, latency_ms = await client.analyze_news(
        symbols=["AAPL"],
        title="Apple reports record profit beat and dividend growth",
        summary="Record quarterly profit driven by strong services margins.",
        content="",
    )

    assert analysis.sentiment > 0.0
    assert analysis.impact == "BULLISH"
    assert analysis.confidence >= 0.70
    assert "AAPL" in analysis.rationale
    assert latency_ms >= 0
