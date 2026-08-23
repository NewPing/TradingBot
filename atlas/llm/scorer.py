"""News article scoring engine with latency tracking, caching, and persistence."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.core.config import get_settings
from atlas.data.models import NewsArticle, NewsScore
from atlas.llm.client import LLMClient
from atlas.llm.prompts import GLOBAL_PROMPT_REGISTRY, VersionedPrompt

logger = logging.getLogger("atlas.llm.scorer")


class NewsScorer:
    """Service to evaluate news articles with local LLM and record versioned scores."""

    def __init__(
        self,
        client: LLMClient | None = None,
        default_prompt_name: str = "news_sentiment",
        default_prompt_version: str = "v1.0",
    ) -> None:
        self.client = client or LLMClient()
        self.default_prompt_name = default_prompt_name
        self.default_prompt_version = default_prompt_version

    async def score_article(
        self,
        article: NewsArticle | dict[str, Any],
        prompt: VersionedPrompt | None = None,
        session: Session | None = None,
    ) -> NewsScore:
        """Score a single news article and persist or return the NewsScore."""
        settings = get_settings()
        prompt_artifact = prompt or GLOBAL_PROMPT_REGISTRY.get(
            self.default_prompt_name, self.default_prompt_version
        )

        if isinstance(article, NewsArticle):
            article_id = article.id
            title = article.title
            summary = article.summary
            content = article.content
            published_at = article.published_at.isoformat()
            try:
                symbols = json.loads(article.symbols) if isinstance(article.symbols, str) else []
            except Exception:
                symbols = []
        else:
            article_id = str(article.get("id") or "")
            title = str(article.get("title") or "")
            summary = str(article.get("summary") or "")
            content = str(article.get("content") or "")
            pub_ts = article.get("published_at")
            published_at = pub_ts.isoformat() if isinstance(pub_ts, datetime) else str(pub_ts or "")
            syms_raw = article.get("symbols") or []
            symbols = [str(s) for s in syms_raw]

        # Check existing cached score in session
        if session and article_id:
            existing = session.scalar(
                select(NewsScore).where(
                    (NewsScore.article_id == article_id)
                    & (NewsScore.prompt_hash == prompt_artifact.prompt_hash)
                )
            )
            if existing:
                return existing

        analysis, latency_ms = await self.client.analyze_news(
            symbols=symbols,
            title=title,
            summary=summary,
            content=content,
            published_at=published_at,
            prompt=prompt_artifact,
        )

        score_rec = NewsScore(
            article_id=article_id,
            model_name=settings.atlas_llm_model,
            prompt_version=prompt_artifact.version,
            prompt_hash=prompt_artifact.prompt_hash,
            sentiment_score=Decimal(str(round(analysis.sentiment, 4))),
            relevance_score=Decimal(str(round(analysis.relevance, 4))),
            horizon=analysis.horizon,
            novelty_score=Decimal(str(round(analysis.novelty, 4))),
            impact=analysis.impact,
            confidence=Decimal(str(round(analysis.confidence, 4))),
            rationale=analysis.rationale,
            scored_at=datetime.now(UTC),
            latency_ms=latency_ms,
        )

        if session and article_id:
            session.add(score_rec)
            session.flush()

        return score_rec

    async def score_articles_batch(
        self,
        articles: list[NewsArticle | dict[str, Any]],
        prompt: VersionedPrompt | None = None,
        session: Session | None = None,
    ) -> list[NewsScore]:
        """Score multiple articles sequentially or in parallel."""
        scores: list[NewsScore] = []
        for article in articles:
            sc = await self.score_article(article, prompt=prompt, session=session)
            scores.append(sc)
        return scores
