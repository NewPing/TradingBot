"""Pydantic v2 API request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from atlas.api.schemas.fundamentals import (
    EarningsEventResponse,
    FundamentalScreenerItem,
    FundamentalScreenerResponse,
    FundamentalSnapshotResponse,
)
from atlas.api.schemas.news import (
    NewsArticleDTO,
    NewsFeedResponse,
    NewsScoreDTO,
    NewsStatsResponse,
    PromptTemplateDTO,
    ScoreNewsRequest,
    SymbolSentimentResponse,
)
from atlas.api.schemas.runs import (
    CompareRequest,
    CompareResponse,
    EquityPointResponse,
    RunCreateRequest,
    RunResponse,
    RunTradeResponse,
)
from atlas.api.schemas.signals import SignalExploreResponse, SignalSeriesPoint
from atlas.api.schemas.trials import TrialBudgetResponse, TrialResponse
from atlas.api.schemas.versions import (
    LineageNode,
    LineageResponse,
    StrategyStatusUpdate,
    StrategyVersionCreate,
    StrategyVersionResponse,
)


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status: ok | degraded | unhealthy")
    timestamp: datetime = Field(..., description="Current UTC timestamp")
    environment: str = Field(..., description="Runtime environment")
    version: str = Field(..., description="Application version")


class VersionResponse(BaseModel):
    version: str
    phase: int
    environment: str
    allow_live: bool


__all__ = [
    "CompareRequest",
    "CompareResponse",
    "EarningsEventResponse",
    "EquityPointResponse",
    "FundamentalScreenerItem",
    "FundamentalScreenerResponse",
    "FundamentalSnapshotResponse",
    "HealthResponse",
    "LineageNode",
    "LineageResponse",
    "NewsArticleDTO",
    "NewsFeedResponse",
    "NewsScoreDTO",
    "NewsStatsResponse",
    "PromptTemplateDTO",
    "RunCreateRequest",
    "RunResponse",
    "RunTradeResponse",
    "ScoreNewsRequest",
    "SignalExploreResponse",
    "SignalSeriesPoint",
    "StrategyStatusUpdate",
    "StrategyVersionCreate",
    "StrategyVersionResponse",
    "SymbolSentimentResponse",
    "TrialBudgetResponse",
    "TrialResponse",
    "VersionResponse",
]
