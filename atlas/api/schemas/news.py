"""Pydantic schemas for news articles, LLM narrative scoring, and prompt templates."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsScoreDTO(BaseModel):
    """Structured LLM analysis score record."""

    id: int | None = None
    article_id: str
    model_name: str
    prompt_version: str
    prompt_hash: str
    sentiment_score: float
    relevance_score: float
    horizon: str
    novelty_score: float
    impact: str
    confidence: float
    rationale: str
    scored_at: datetime
    latency_ms: int


class NewsArticleDTO(BaseModel):
    """Financial news article with optional attached LLM score."""

    id: str
    source: str
    url: str
    title: str
    summary: str
    content: str
    published_at: datetime
    symbols: list[str]
    content_hash: str
    score: NewsScoreDTO | None = None


class NewsFeedResponse(BaseModel):
    """Paginated news feed response."""

    total: int
    articles: list[NewsArticleDTO]


class SymbolSentimentResponse(BaseModel):
    """Aggregated narrative and LLM sentiment profile for a symbol."""

    symbol: str
    composite_sentiment: float
    narrative_momentum: float
    article_count_24h: int
    article_count_72h: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    latest_catalyst: str
    sentiment_label: str


class ScoreNewsRequest(BaseModel):
    """On-demand article scoring request payload."""

    symbols: list[str] = Field(default_factory=list)
    title: str
    summary: str
    content: str = ""
    published_at: str | None = None
    prompt_version: str = "v1.0"


class PromptTemplateDTO(BaseModel):
    """Versioned prompt artifact description."""

    name: str
    version: str
    prompt_hash: str
    system_prompt: str
    user_template: str
    schema_definition: str
    is_active: bool


class NewsStatsResponse(BaseModel):
    """System-level narrative scoring and inference telemetry."""

    total_articles: int
    scored_articles: int
    llm_model: str
    llm_base_url: str
    active_prompt_version: str
    active_prompt_hash: str
    avg_latency_ms: float
    p95_latency_ms: float
    allow_short: bool
    status: str
