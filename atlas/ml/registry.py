"""Model Artifact Schema, Serialization, and Versioned Registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from atlas.ml.explain import PredictionExplanation, ShapExplainer


class ModelMetadata(BaseModel):
    """Metadata describing a serialized statistical/ML model artifact."""

    model_id: str
    version: str = "1.0.0"
    model_type: str = "lightgbm_classifier"  # lightgbm_classifier, lightgbm_regressor
    target_name: str = "target_dir_5d"
    target_horizon_days: int = 5
    feature_names: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    train_date_range: list[str] = Field(default_factory=lambda: ["2005-01-01", "2018-12-31"])
    metrics: dict[str, float] = Field(default_factory=dict)
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    feature_importances: dict[str, float] = Field(default_factory=dict)


class ModelArtifact:
    """Executable wrapper around a trained ML model, its metadata, and explainability engine."""

    def __init__(self, model: Any, metadata: ModelMetadata) -> None:
        self.model = model
        self.metadata = metadata
        self.explainer = ShapExplainer(model, metadata.feature_names)

    def predict(self, features: dict[str, float]) -> tuple[float, PredictionExplanation]:
        """Generate score and feature attribution rationale for a single point-in-time observation.

        Returns:
            (score, explanation) where score is in [-1.0 .. +1.0].
        """
        import numpy as np

        feat_vector = np.array(
            [[features.get(k, 0.0) for k in self.metadata.feature_names]], dtype=float
        )

        if self.metadata.model_type == "lightgbm_classifier":
            # Predict class 1 probability (0.0 .. 1.0) -> mapped to normalized score (-1.0 .. +1.0)
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(feat_vector)
                prob_up = float(probs[0, 1]) if probs.shape[1] > 1 else float(probs[0, 0])
            else:
                raw = float(self.model.predict(feat_vector)[0])
                prob_up = 1.0 / (1.0 + np.exp(-raw))
            # Rescale probability [0.0..1.0] to score [-1.0..+1.0]
            score = (prob_up - 0.5) * 2.0
        else:
            # Regressor predicts continuous expected forward return
            pred_return = float(self.model.predict(feat_vector)[0])
            # Tanh squashing to [-1.0 .. +1.0]
            score = float(np.tanh(pred_return * 20.0))

        score = max(-1.0, min(1.0, score))
        explanation = self.explainer.explain_instance(features, score)
        return score, explanation


class ModelRegistry:
    """Manages versioned persistence and retrieval of trained model artifacts."""

    DEFAULT_DIR = Path("data/models")

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or self.DEFAULT_DIR

    def save(self, artifact: ModelArtifact) -> Path:
        """Save model artifact and metadata to disk."""
        model_dir = self.base_dir / artifact.metadata.model_id / artifact.metadata.version
        model_dir.mkdir(parents=True, exist_ok=True)

        meta_path = model_dir / "metadata.json"
        model_path = model_dir / "model.joblib"

        with meta_path.open("w", encoding="utf-8") as f:
            f.write(artifact.metadata.model_dump_json(indent=2))

        joblib.dump(artifact.model, model_path)
        return model_dir

    def load(self, model_id: str, version: str = "1.0.0") -> ModelArtifact:
        """Load model artifact from disk."""
        if version == "latest":
            parent = self.base_dir / model_id
            if not parent.exists():
                raise FileNotFoundError(f"Model directory not found: {parent}")
            versions = sorted([d.name for d in parent.iterdir() if d.is_dir()])
            if not versions:
                raise FileNotFoundError(f"No versions found for model {model_id}")
            version = versions[-1]

        model_dir = self.base_dir / model_id / version
        meta_path = model_dir / "metadata.json"
        model_path = model_dir / "model.joblib"

        if not meta_path.exists() or not model_path.exists():
            raise FileNotFoundError(f"Artifact not found at {model_dir}")

        with meta_path.open(encoding="utf-8") as f:
            meta_dict = json.load(f)

        metadata = ModelMetadata(**meta_dict)
        model = joblib.load(model_path)
        return ModelArtifact(model=model, metadata=metadata)

    def list_models(self) -> list[ModelMetadata]:
        """List all available registered models and their versions."""
        if not self.base_dir.exists():
            return []

        results: list[ModelMetadata] = []
        for model_dir in self.base_dir.iterdir():
            if not model_dir.is_dir():
                continue
            for v_dir in model_dir.iterdir():
                if not v_dir.is_dir():
                    continue
                meta_path = v_dir / "metadata.json"
                if meta_path.exists():
                    try:
                        with meta_path.open(encoding="utf-8") as f:
                            meta_dict = json.load(f)
                        results.append(ModelMetadata(**meta_dict))
                    except Exception:
                        continue
        return results
