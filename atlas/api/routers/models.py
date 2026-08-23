"""FastAPI router for ML Model Registry, SHAP Explainability, and Market Regimes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import polars as pl
from fastapi import APIRouter, HTTPException, Query, status

from atlas.api.schemas.models import (
    FeatureDriver,
    ModelDetailResponse,
    ModelPredictRequest,
    ModelPredictResponse,
    RegimeResponse,
)
from atlas.core.clock import SimClock
from atlas.core.context import HistoricalMarketContext
from atlas.core.types import Symbol
from atlas.ml.models import ModelRegistry
from atlas.signals.regime import RegimeDetector

router = APIRouter(prefix="/api/v1/models", tags=["Machine Learning & Regimes"])


@router.get("", response_model=list[ModelDetailResponse])
def list_models() -> list[ModelDetailResponse]:
    """List all registered ML models and their versions."""
    registry = ModelRegistry()
    models = registry.list_models()
    return [
        ModelDetailResponse(
            model_id=m.model_id,
            version=m.version,
            model_type=m.model_type,
            target_name=m.target_name,
            target_horizon_days=m.target_horizon_days,
            feature_names=m.feature_names,
            created_at=m.created_at,
            train_date_range=m.train_date_range,
            metrics=m.metrics,
            hyperparameters=m.hyperparameters,
            feature_importances=m.feature_importances,
        )
        for m in models
    ]


@router.get("/regime/current", response_model=RegimeResponse)
def get_current_regime(
    benchmark: Annotated[str, Query(description="Benchmark symbol (e.g. SPY)")] = "SPY",
) -> RegimeResponse:
    """Get current market regime classification and plain-English rationale."""
    bench_sym = Symbol(benchmark.upper())
    detector = RegimeDetector(default_benchmark=benchmark)

    clock = SimClock(datetime.now(UTC))
    ctx = HistoricalMarketContext(clock=clock, bars_df=pl.DataFrame())
    state = detector.classify(ctx, benchmark=bench_sym)

    return RegimeResponse(
        trend=state.trend.value,
        volatility=state.volatility.value,
        quadrant=state.quadrant.value,
        trend_score=state.trend_score,
        vol_score=state.vol_score,
        confidence=state.confidence,
        breadth_pct_50d=state.breadth_pct_50d,
        breadth_pct_200d=state.breadth_pct_200d,
        realized_vol_21d=state.realized_vol_21d,
        benchmark_symbol=str(state.benchmark_symbol),
        rationale=state.rationale,
    )


@router.post("/predict", response_model=ModelPredictResponse)
def predict_model(req: ModelPredictRequest) -> ModelPredictResponse:
    """Run model inference on input features and return score with SHAP attribution rationale."""
    registry = ModelRegistry()
    try:
        artifact = registry.load(req.model_id, req.version)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {req.model_id}:{req.version} not found in registry",
        ) from err

    score, expl = artifact.predict(req.features)
    conf = 0.5 + abs(score) * 0.45

    pos_drivers = [FeatureDriver(feature=name, shap_value=val) for name, val in expl.top_positive]
    neg_drivers = [FeatureDriver(feature=name, shap_value=val) for name, val in expl.top_negative]

    return ModelPredictResponse(
        model_id=req.model_id,
        version=req.version,
        score=score,
        confidence=conf,
        base_value=expl.base_value,
        top_positive=pos_drivers,
        top_negative=neg_drivers,
        rationale=expl.rationale,
    )


@router.get("/{model_id}/{version}", response_model=ModelDetailResponse)
def get_model(model_id: str, version: str = "1.0.0") -> ModelDetailResponse:
    """Retrieve detailed metadata and feature importances for a specific model version."""
    registry = ModelRegistry()
    try:
        artifact = registry.load(model_id, version)
    except FileNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id}:{version} not found in registry",
        ) from err

    m = artifact.metadata
    return ModelDetailResponse(
        model_id=m.model_id,
        version=m.version,
        model_type=m.model_type,
        target_name=m.target_name,
        target_horizon_days=m.target_horizon_days,
        feature_names=m.feature_names,
        created_at=m.created_at,
        train_date_range=m.train_date_range,
        metrics=m.metrics,
        hyperparameters=m.hyperparameters,
        feature_importances=m.feature_importances,
    )
