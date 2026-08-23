"""LightGBM Model Training and Purged Cross-Validation Pipeline."""

from __future__ import annotations

from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score  # type: ignore[import-untyped]

from atlas.ml.models import ModelArtifact, ModelMetadata
from atlas.ml.registry import ModelRegistry
from atlas.ml.validation import PurgedKFoldCV


class MLTrainer:
    """Trains and validates gradient-boosted trees using Purged K-Fold CV."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()

    def train_classifier(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        target_col: str,
        model_id: str = "lgbm_dir_5d_v1",
        version: str = "1.0.0",
        target_horizon_days: int = 5,
        n_splits: int = 5,
        params: dict[str, Any] | None = None,
    ) -> ModelArtifact:
        """Train and validate a LightGBM directional classifier with Purged CV."""
        # 1. Clean data: drop rows with NaNs in features or target
        clean_df = df.dropna(subset=feature_cols + [target_col]).copy()
        if len(clean_df) < 100:
            raise ValueError(f"Insufficient training samples ({len(clean_df)}) for ML training")

        X = clean_df[feature_cols].to_numpy(dtype=float)
        y = clean_df[target_col].to_numpy(dtype=int)

        # 2. Setup hyperparameters
        default_params: dict[str, Any] = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "n_estimators": 100,
            "learning_rate": 0.05,
            "max_depth": 4,
            "num_leaves": 15,
            "min_child_samples": 20,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "verbose": -1,
        }
        if params:
            default_params.update(params)

        # 3. Purged K-Fold Cross-Validation
        cv = PurgedKFoldCV(n_splits=n_splits, embargo_bars=target_horizon_days)
        oof_preds = np.zeros(len(clean_df))
        fold_aucs: list[float] = []
        fold_accs: list[float] = []

        for train_idx, test_idx in cv.split(clean_df):
            if len(train_idx) < 20 or len(test_idx) < 10:
                continue

            X_tr, y_tr = X[train_idx], y[train_idx]
            X_te, y_te = X[test_idx], y[test_idx]

            fold_model = lgb.LGBMClassifier(**default_params)
            fold_model.fit(X_tr, y_tr)

            probs = np.asarray(fold_model.predict_proba(X_te))[:, 1]
            oof_preds[test_idx] = probs

            try:
                auc = float(roc_auc_score(y_te, probs))
                fold_aucs.append(auc)
            except Exception:
                pass

            preds_binary = (probs > 0.5).astype(int)
            fold_accs.append(float(accuracy_score(y_te, preds_binary)))

        # 4. Train final model on full dataset
        final_model = lgb.LGBMClassifier(**default_params)
        final_model.fit(X, y)

        # Compute feature importances
        raw_importances = final_model.feature_importances_
        tot_imp = float(np.sum(raw_importances)) if np.sum(raw_importances) > 0 else 1.0
        normalized_importances = {
            feat: float(imp / tot_imp)
            for feat, imp in zip(feature_cols, raw_importances, strict=False)
        }

        # Date range
        start_date = "2005-01-01"
        end_date = "2018-12-31"
        if "timestamp" in clean_df.columns:
            start_date = str(pd.to_datetime(clean_df["timestamp"].min()).date())
            end_date = str(pd.to_datetime(clean_df["timestamp"].max()).date())

        metrics = {
            "cv_roc_auc": float(np.mean(fold_aucs)) if fold_aucs else 0.5,
            "cv_accuracy": float(np.mean(fold_accs)) if fold_accs else 0.5,
            "n_samples": float(len(clean_df)),
            "n_features": float(len(feature_cols)),
        }

        metadata = ModelMetadata(
            model_id=model_id,
            version=version,
            model_type="lightgbm_classifier",
            target_name=target_col,
            target_horizon_days=target_horizon_days,
            feature_names=feature_cols,
            train_date_range=[start_date, end_date],
            metrics=metrics,
            hyperparameters=default_params,
            feature_importances=normalized_importances,
        )

        artifact = ModelArtifact(model=final_model, metadata=metadata)
        self.registry.save(artifact)
        return artifact
