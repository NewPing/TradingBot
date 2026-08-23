"""Pydantic schemas for Strategy Version API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StrategyVersionResponse(BaseModel):
    id: str
    family: str
    version: str
    spec_hash: str
    git_sha: str | None = None
    parent_id: str | None = None
    status: str
    notes: str = ""
    created_at: datetime
    spec_yaml: str | None = None


class StrategyVersionCreate(BaseModel):
    spec_yaml: str
    notes: str = ""
    status: str = "RESEARCH"


class StrategyStatusUpdate(BaseModel):
    status: str
    notes: str = ""


class LineageNode(BaseModel):
    id: str
    family: str
    version: str
    status: str
    spec_hash: str
    created_at: str


class LineageResponse(BaseModel):
    current: LineageNode
    ancestors: list[LineageNode] = Field(default_factory=list)
    children: list[LineageNode] = Field(default_factory=list)
