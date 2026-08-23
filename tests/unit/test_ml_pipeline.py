"""Unit tests for ML pipeline, LightGBM training, Model Registry, and SHAP explainability."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from atlas.ml.explain import ShapExplainer
from atlas.ml.pipeline import MLTrainer
from atlas.ml.registry import ModelRegistry


def test_model_registry_save_and_load() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        registry = ModelRegistry(base_path)

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2010-01-01", periods=200, freq="B"),
                "feat1": np.random.randn(200),
                "feat2": np.random.randn(200),
                "target_dir_5d": np.random.choice([0, 1], size=200),
            }
        )

        trainer = MLTrainer(registry=registry)
        artifact = trainer.train_classifier(
            df=df,
            feature_cols=["feat1", "feat2"],
            target_col="target_dir_5d",
            model_id="test_lgbm_model",
            version="1.0.0",
        )

        assert artifact is not None
        assert artifact.metadata.model_id == "test_lgbm_model"
        assert len(artifact.metadata.feature_importances) == 2

        # Test loading
        loaded = registry.load("test_lgbm_model", "1.0.0")
        assert loaded.metadata.model_id == "test_lgbm_model"

        # Test inference and explainability
        score, expl = loaded.predict({"feat1": 0.5, "feat2": -0.2})
        assert -1.0 <= score <= 1.0
        assert len(expl.rationale) > 0


def test_shap_explainer_local_attribution() -> None:
    import lightgbm as lgb

    X = np.random.randn(100, 3)
    y = np.random.choice([0, 1], size=100)
    model = lgb.LGBMClassifier(n_estimators=10, random_state=42, verbose=-1)
    model.fit(X, y)

    explainer = ShapExplainer(model, ["feat_a", "feat_b", "feat_c"])
    expl = explainer.explain_instance({"feat_a": 1.2, "feat_b": -0.5, "feat_c": 0.1}, 0.6)

    assert expl.output_value == 0.6
    assert isinstance(expl.rationale, str)
