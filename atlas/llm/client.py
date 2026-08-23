"""Async client for local LLM inference (vLLM / llama-swap) with structured JSON enforcement."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal

import httpx

from atlas.core.config import get_settings
from atlas.llm.prompts import GLOBAL_PROMPT_REGISTRY, LLMNewsAnalysis, VersionedPrompt

logger = logging.getLogger("atlas.llm.client")


class LLMClient:
    """Async client for local LLM inference with latency tracking and structured output validation."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 5.0,
        max_retries: int = 2,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.atlas_llm_base_url).rstrip("/")
        self.model = model or settings.atlas_llm_model
        self.timeout = timeout
        self.max_retries = max_retries

    async def is_available(self) -> bool:
        """Check if LLM inference endpoint is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/models")
                return res.status_code == 200
        except Exception:
            return False

    async def analyze_news(
        self,
        symbols: list[str],
        title: str,
        summary: str,
        content: str = "",
        published_at: str = "",
        prompt: VersionedPrompt | None = None,
    ) -> tuple[LLMNewsAnalysis, int]:
        """Analyze a financial news item and return validated structured JSON with latency_ms."""
        prompt_artifact = prompt or GLOBAL_PROMPT_REGISTRY.get("news_sentiment", "v1.0")
        symbols_str = ", ".join(symbols) if symbols else "MARKET_WIDE"

        user_content = prompt_artifact.user_template.format(
            symbols=symbols_str,
            published_at=published_at,
            title=title,
            summary=summary,
            content=content[:1500] if content else summary,  # truncate very long articles
        )

        messages = [
            {"role": "system", "content": prompt_artifact.system_prompt},
            {"role": "user", "content": user_content},
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        t_start = time.perf_counter()
        raw_response_text = ""
        success = False

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices") or []
                        if choices:
                            raw_response_text = choices[0].get("message", {}).get("content", "")
                            success = True
                            break
            except Exception as exc:
                logger.debug("LLM inference attempt %d failed: %s", attempt + 1, exc)
                if attempt == self.max_retries:
                    break

        latency_ms = int((time.perf_counter() - t_start) * 1000)

        if success and raw_response_text:
            try:
                parsed_json = self._extract_json(raw_response_text)
                return LLMNewsAnalysis.model_validate(parsed_json), latency_ms
            except Exception as e:
                logger.warning("Failed to validate LLM structured response: %s", e)

        # Fallback heuristic analysis for disconnected/offline environments
        fallback_analysis = self._generate_heuristic_fallback(
            symbols=symbols,
            title=title,
            summary=summary,
            content=content,
        )
        return fallback_analysis, latency_ms

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM output string."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Regex fallback to find outermost JSON object
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError(f"Extracted payload is not a JSON object: {type(data)}")

    @staticmethod
    def _generate_heuristic_fallback(
        symbols: list[str],
        title: str,
        summary: str,
        content: str,
    ) -> LLMNewsAnalysis:
        """Deterministic keyword-based analysis when offline or LLM server is unreachable."""
        combined_text = f"{title} {summary} {content}".lower()

        bullish_words = [
            "record",
            "beat",
            "growth",
            "surpass",
            "upgrade",
            "buy",
            "outperform",
            "profit",
            "rally",
            "soar",
            "gain",
            "dividend increase",
            "partnership",
            "fda approved",
        ]
        bearish_words = [
            "miss",
            "plunge",
            "downgrade",
            "lawsuit",
            "investigation",
            "drop",
            "loss",
            "cut",
            "warning",
            "decline",
            "slump",
            "bankruptcy",
            "default",
            "fraud",
        ]

        bull_count = sum(1 for word in bullish_words if word in combined_text)
        bear_count = sum(1 for word in bearish_words if word in combined_text)

        raw_sentiment = 0.0
        impact: Literal["BULLISH", "BEARISH", "NEUTRAL"]
        if bull_count > bear_count:
            raw_sentiment = min(1.0, 0.25 + 0.15 * (bull_count - bear_count))
            impact = "BULLISH"
        elif bear_count > bull_count:
            raw_sentiment = max(-1.0, -0.25 - 0.15 * (bear_count - bull_count))
            impact = "BEARISH"
        else:
            impact = "NEUTRAL"

        relevance = 0.8 if symbols else 0.4
        sym_str = ", ".join(symbols) if symbols else "general market"

        return LLMNewsAnalysis(
            sentiment=round(raw_sentiment, 4),
            relevance=relevance,
            horizon="SHORT_TERM",
            novelty=0.6,
            impact=impact,
            confidence=0.75,
            rationale=f"Heuristic evaluation for {sym_str}: identified {bull_count} positive and {bear_count} negative catalytic signals.",
        )
