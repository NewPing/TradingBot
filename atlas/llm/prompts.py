"""Prompt templates, hash registry, and structured output schemas for LLM scoring."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class LLMNewsAnalysis(BaseModel):
    """Strict structured JSON output contract returned by LLM news scoring."""

    sentiment: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Sentiment score from -1.0 (extremely negative/bearish) to +1.0 (extremely positive/bullish).",
    )
    relevance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score from 0.0 (irrelevant/macro noise) to 1.0 (directly material to company fundamentals).",
    )
    horizon: Literal["INTRADAY", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"] = Field(
        default="SHORT_TERM",
        description="Expected time horizon of impact.",
    )
    novelty: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Novelty score from 0.0 (old news/rehash) to 1.0 (breaking unexpected catalyst).",
    )
    impact: Literal["BULLISH", "BEARISH", "NEUTRAL"] = Field(
        default="NEUTRAL",
        description="Categorical market impact classification.",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Model confidence in analysis from 0.0 to 1.0.",
    )
    rationale: str = Field(
        ...,
        description="Concise 1-3 sentence institutional rationale explaining why this news impacts the equity.",
    )


DEFAULT_SYSTEM_PROMPT_V1 = """You are ATLAS-LLM, a quantitative equity research analyst scoring financial news for institutional trading strategies.
Analyze the provided news article for the target equity symbol(s).
Evaluate the material financial impact, sentiment, novelty, and time horizon.

Return ONLY a valid JSON object strictly matching this schema:
{
  "sentiment": <float from -1.0 (maximum bearish) to +1.0 (maximum bullish)>,
  "relevance": <float from 0.0 (immaterial/noise) to 1.0 (direct fundamental driver)>,
  "horizon": "<INTRADAY | SHORT_TERM | MEDIUM_TERM | LONG_TERM>",
  "novelty": <float from 0.0 (stale/reiterated) to 1.0 (breaking unexpected catalyst)>,
  "impact": "<BULLISH | BEARISH | NEUTRAL>",
  "confidence": <float from 0.0 to 1.0>,
  "rationale": "<Concise 1-3 sentence factual explanation of the market impact>"
}
"""

DEFAULT_USER_TEMPLATE_V1 = """TARGET SYMBOLS: {symbols}
PUBLISHED TIME (UTC): {published_at}
HEADLINE: {title}
SUMMARY: {summary}
CONTENT: {content}

Provide your structured JSON evaluation now."""


@dataclass(frozen=True, slots=True)
class VersionedPrompt:
    """Immutable versioned prompt artifact."""

    name: str
    version: str
    system_prompt: str
    user_template: str
    schema_json: str
    prompt_hash: str


class PromptRegistry:
    """Registry maintaining immutable prompt version artifacts and hashes."""

    def __init__(self) -> None:
        self._prompts: dict[str, VersionedPrompt] = {}
        self._register_defaults()

    @staticmethod
    def compute_hash(system_prompt: str, user_template: str, schema_json: str) -> str:
        """Compute SHA-256 hash of prompt template and schema definition."""
        hasher = hashlib.sha256()
        payload = f"{system_prompt}\n---\n{user_template}\n---\n{schema_json}".encode()
        hasher.update(payload)
        return hasher.hexdigest()

    def register(
        self,
        name: str,
        version: str,
        system_prompt: str,
        user_template: str,
        schema_json: str | None = None,
    ) -> VersionedPrompt:
        """Register a versioned prompt artifact."""
        schema_str = schema_json or json.dumps(LLMNewsAnalysis.model_json_schema())
        p_hash = self.compute_hash(system_prompt, user_template, schema_str)
        prompt = VersionedPrompt(
            name=name,
            version=version,
            system_prompt=system_prompt,
            user_template=user_template,
            schema_json=schema_str,
            prompt_hash=p_hash,
        )
        self._prompts[f"{name}:{version}"] = prompt
        return prompt

    def get(self, name: str = "news_sentiment", version: str = "v1.0") -> VersionedPrompt:
        """Lookup versioned prompt."""
        key = f"{name}:{version}"
        if key not in self._prompts:
            raise KeyError(f"Prompt '{key}' not found in registry")
        return self._prompts[key]

    def list_prompts(self) -> list[VersionedPrompt]:
        """List all registered prompt versions."""
        return list(self._prompts.values())

    def _register_defaults(self) -> None:
        schema_str = json.dumps(LLMNewsAnalysis.model_json_schema())
        self.register(
            name="news_sentiment",
            version="v1.0",
            system_prompt=DEFAULT_SYSTEM_PROMPT_V1,
            user_template=DEFAULT_USER_TEMPLATE_V1,
            schema_json=schema_str,
        )


GLOBAL_PROMPT_REGISTRY = PromptRegistry()
