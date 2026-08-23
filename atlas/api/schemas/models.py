"""Pydantic schemas for Machine Learning models and Regime APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegimeResponse(BaseModel):
    trend: str
    volatility: str
    quadrant: str
    trend_score: float
    vol_score: float
    confidence: float
    breadth_pct_50d: float
    breadth_pct_200d: float
    realized_vol_21d: float
    benchmark_symbol: str
    rationale: str


class ModelDetailResponse(BaseModel):
    model_id: str
    version: str
    model_type: str
    target_name: str
    target_horizon_days: int
    feature_names: list[str] = Field(default_factory=list)
    created_at: str
    train_date_range: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    feature_importances: dict[str, float] = Field(default_factory=dict)


class ModelPredictRequest(BaseModel):
    model_id: str = "lgbm_dir_5d_v1"
    version: str = "1.0.0"
    features: dict[str, float] = Field(default_factory=dict)


class FeatureDriver(BaseModel):
    feature: str
    shap_value: float


class ModelPredictResponse(BaseModel):
    model_id: str
    version: str
    score: float
    confidence: float
    base_value: float
    top_positive: list[FeatureDriver] = Field(default_factory=list)
    top_negative: list[FeatureDriver] = Field(default_factory=list)
    rationale: str
