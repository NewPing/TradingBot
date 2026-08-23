"""Bootstrap default model artifacts for L2 signals and model registry."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from atlas.core.types import Symbol
from atlas.ml.models import ModelArtifact
from atlas.ml.pipeline import MLTrainer
from atlas.ml.registry import ModelRegistry
from atlas.signals.features.extractor import FeatureEngine


def bootstrap_default_lgbm_model(
    model_id: str = "lgbm_dir_5d_v1",
    version: str = "1.0.0",
    registry_dir: Path | None = None,
) -> ModelArtifact:
    """Bootstrap and train the baseline LightGBM model artifact on canonical features."""
    registry = ModelRegistry(registry_dir)
    try:
        return registry.load(model_id, version)
    except (FileNotFoundError, Exception):
        pass

    # Generate multi-regime training dataset (2005-2018 simulated train partition)
    np.random.seed(42)
    n_days = 2500
    dates = pd.date_range("2005-01-03", periods=n_days, freq="B")

    # Generate realistic price paths with regime transitions
    rets = np.random.normal(0.0004, 0.012, n_days)
    # Add trending and momentum clusters
    for i in range(20, n_days):
        rets[i] += 0.05 * rets[i - 1]
    prices = 100.0 * np.exp(np.cumsum(rets))
    raw_highs = prices * (1.0 + np.abs(np.random.normal(0.005, 0.004, n_days)))
    raw_lows = prices * (1.0 - np.abs(np.random.normal(0.005, 0.004, n_days)))
    opens = prices * (1.0 + np.random.normal(0.0, 0.003, n_days))
    highs = np.maximum(np.maximum(prices, opens), raw_highs)
    lows = np.minimum(np.minimum(prices, opens), raw_lows)
    volumes = np.random.lognormal(14.0, 0.5, n_days)

    df_bars = pd.DataFrame(
        {
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        }
    )

    feat_engine = FeatureEngine()
    dataset = feat_engine.build_dataset_from_bars(
        symbol_bars_map={Symbol("SPY"): df_bars, Symbol("QQQ"): df_bars},
        forward_horizons=[5],
    )

    feature_cols = feat_engine.stat_extractor.feature_names

    trainer = MLTrainer(registry=registry)
    artifact = trainer.train_classifier(
        df=dataset,
        feature_cols=feature_cols,
        target_col="target_dir_5d",
        model_id=model_id,
        version=version,
        target_horizon_days=5,
        n_splits=5,
    )
    return artifact


if __name__ == "__main__":
    artifact = bootstrap_default_lgbm_model()
    print(
        f"Bootstrapped {artifact.metadata.model_id} v{artifact.metadata.version} with {len(artifact.metadata.feature_names)} features."
    )
