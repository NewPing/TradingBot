"""SHAP Explainability and Feature Attribution Engine for ML Signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PredictionExplanation:
    """Detailed feature contribution breakdown for a single point-in-time prediction."""

    base_value: float
    output_value: float
    top_positive: list[tuple[str, float]]  # (feature_name, shap_value)
    top_negative: list[tuple[str, float]]  # (feature_name, shap_value)
    rationale: str  # Concise plain-English summary for Signal.rationale


class ShapExplainer:
    """Wraps TreeExplainer for fast point-in-time feature attribution."""

    def __init__(self, model: Any, feature_names: list[str]) -> None:
        self.feature_names = feature_names
        self._tree_explainer: Any = None
        self._has_shap = False

        try:
            import shap  # type: ignore[import-untyped]

            self._tree_explainer = shap.TreeExplainer(model)
            self._has_shap = True
        except Exception:
            self._has_shap = False

    def explain_instance(
        self,
        features_dict: dict[str, float],
        prediction_val: float,
        top_k: int = 3,
    ) -> PredictionExplanation:
        """Compute local feature attributions for a single observation."""
        feat_vector = np.array(
            [[features_dict.get(name, 0.0) for name in self.feature_names]], dtype=float
        )

        if self._has_shap and self._tree_explainer is not None:
            try:
                shap_vals = self._tree_explainer.shap_values(feat_vector)
                # Handle binary classification (2-class output) vs regression
                if isinstance(shap_vals, list) and len(shap_vals) == 2:
                    vals = np.array(shap_vals[1][0], dtype=float)
                    base_val = (
                        float(self._tree_explainer.expected_value[1])
                        if isinstance(self._tree_explainer.expected_value, (list, np.ndarray))
                        else float(self._tree_explainer.expected_value)
                    )
                elif isinstance(shap_vals, np.ndarray):
                    if shap_vals.ndim == 3:  # (samples, features, classes)
                        vals = np.array(
                            shap_vals[0, :, 1] if shap_vals.shape[2] > 1 else shap_vals[0, :, 0],
                            dtype=float,
                        )
                    elif shap_vals.ndim == 2:
                        vals = np.array(shap_vals[0], dtype=float)
                    else:
                        vals = np.array(shap_vals, dtype=float)
                    base_val = (
                        float(self._tree_explainer.expected_value)
                        if not isinstance(self._tree_explainer.expected_value, (list, np.ndarray))
                        else float(self._tree_explainer.expected_value[0])
                    )
                else:
                    vals = np.zeros(len(self.feature_names))
                    base_val = 0.5
            except Exception:
                vals = np.zeros(len(self.feature_names))
                base_val = 0.5
        else:
            # Fallback zero attribution
            vals = np.zeros(len(self.feature_names))
            base_val = 0.5

        # Pair features with their attribution values
        paired = list(zip(self.feature_names, vals, strict=False))
        pos_drivers = sorted(
            [(k, float(v)) for k, v in paired if v > 0.001], key=lambda x: x[1], reverse=True
        )[:top_k]
        neg_drivers = sorted([(k, float(v)) for k, v in paired if v < -0.001], key=lambda x: x[1])[
            :top_k
        ]

        # Construct concise plain-English rationale
        reasons: list[str] = []
        if pos_drivers:
            pos_str = ", ".join([f"{name} (+{score:.2f})" for name, score in pos_drivers])
            reasons.append(f"Bullish drivers: {pos_str}")
        if neg_drivers:
            neg_str = ", ".join([f"{name} ({score:.2f})" for name, score in neg_drivers])
            reasons.append(f"Bearish drags: {neg_str}")

        if not reasons:
            rationale = (
                f"Neutral ML prediction ({prediction_val:.2f}) based on balanced feature inputs."
            )
        else:
            rationale = f"ML score {prediction_val:.2f} | " + " | ".join(reasons)

        return PredictionExplanation(
            base_value=base_val,
            output_value=prediction_val,
            top_positive=pos_drivers,
            top_negative=neg_drivers,
            rationale=rationale,
        )
