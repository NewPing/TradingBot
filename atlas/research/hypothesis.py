"""Autonomous hypothesis generator and strategy discovery engine (Phase 8).

Generates novel strategy specifications and parameter variants across 5 modalities:
1. Parameter Refinement (fine-tuning around known-good parameter topologies)
2. Feature Combination (incorporating multi-layer features L1-L4)
3. Regime-Conditional Variants (regime-aware filter weights)
4. Universe / Timeframe Variation (expanding or focusing instrument universes)
5. Genetic Recombination (crossing over elite components from top lineages)
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import uuid
from decimal import Decimal
from typing import Any

import yaml

from atlas.strategies.spec import StrategySpec


class HypothesisGenerator:
    """Generates candidate hypotheses for the autonomous research loop."""

    @staticmethod
    def _hash_spec(spec_dict: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of a strategy spec dictionary."""
        canonical_str = json.dumps(spec_dict, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def generate_parameter_refinement(
        self,
        base_spec: StrategySpec,
        param_jitter: float = 0.20,
    ) -> dict[str, Any]:
        """Refine numeric parameters of an existing base specification."""
        spec_data = copy.deepcopy(base_spec.model_dump(mode="json"))

        # Jitter numeric parameters in signals
        modified_signals = []
        for s in spec_data.get("signals", []):
            s_copy = copy.deepcopy(s)
            params = s_copy.get("params", {})
            for k, v in list(params.items()):
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    factor = 1.0 + random.uniform(-param_jitter, param_jitter)
                    if isinstance(v, int):
                        params[k] = max(1, int(round(v * factor)))
                    else:
                        params[k] = round(float(v * factor), 4)
            s_copy["params"] = params
            modified_signals.append(s_copy)

        spec_data["signals"] = modified_signals
        variant_id = str(uuid.uuid4())[:8]
        spec_data["name"] = f"{base_spec.name}_ref_{variant_id}"

        spec_yaml = yaml.dump(spec_data, sort_keys=False)
        spec_hash = self._hash_spec(spec_data)

        return {
            "id": f"hyp_ref_{variant_id}",
            "family": base_spec.family,
            "generator_type": "PARAM_REFINEMENT",
            "title": f"Parameter Refinement of {base_spec.name} (±{int(param_jitter * 100)}% jitter)",
            "description": f"Exploring parameter neighborhood around {base_spec.name} to optimize signal efficiency.",
            "base_spec_name": base_spec.name,
            "proposed_spec": spec_yaml,
            "spec_hash": spec_hash,
            "prior_score": Decimal("0.75"),
        }

    def generate_feature_combination(
        self,
        base_spec: StrategySpec,
        layer: str = "l2",  # l2 | l3 | l4
    ) -> dict[str, Any]:
        """Incorporate higher-layer signal features into a baseline strategy."""
        spec_data = copy.deepcopy(base_spec.model_dump(mode="json"))
        signals = list(spec_data.get("signals", []))

        if layer == "l2":
            new_signal = {
                "provider": "l2_cross_sectional_momentum",
                "weight": 0.25,
                "params": {"lookback_days": 60, "top_quantile": 0.2},
            }
        elif layer == "l3":
            new_signal = {
                "provider": "l3_composite_fundamental",
                "weight": 0.20,
                "params": {"min_quality_score": 0.6, "pe_percentile_max": 0.4},
            }
        else:  # l4
            new_signal = {
                "provider": "l4_news_sentiment",
                "weight": 0.15,
                "params": {"lookback_hours": 48, "min_relevance": 0.6},
            }

        # Normalize weights
        signals.append(new_signal)
        total_w = sum(float(s.get("weight", 1.0)) for s in signals)
        for s in signals:
            s["weight"] = round(float(s.get("weight", 1.0)) / total_w, 3)

        spec_data["signals"] = signals
        variant_id = str(uuid.uuid4())[:8]
        spec_data["name"] = f"{base_spec.name}_{layer}_{variant_id}"

        spec_yaml = yaml.dump(spec_data, sort_keys=False)
        spec_hash = self._hash_spec(spec_data)

        return {
            "id": f"hyp_feat_{variant_id}",
            "family": base_spec.family,
            "generator_type": "FEATURE_COMBO",
            "title": f"Feature Enhancement with {layer.upper()} Signal on {base_spec.name}",
            "description": f"Enriches {base_spec.name} with {new_signal['provider']} to capture cross-layer alpha.",
            "base_spec_name": base_spec.name,
            "proposed_spec": spec_yaml,
            "spec_hash": spec_hash,
            "prior_score": Decimal("0.85"),
        }

    def generate_regime_variant(
        self,
        base_spec: StrategySpec,
    ) -> dict[str, Any]:
        """Generate regime-conditional filtering and volatility targeting for base spec."""
        spec_data = copy.deepcopy(base_spec.model_dump(mode="json"))
        signals = list(spec_data.get("signals", []))
        signals.append(
            {
                "provider": "l2_regime_detector",
                "weight": 0.30,
                "params": {"bull_multiplier": 1.2, "bear_multiplier": 0.4},
            }
        )

        total_w = sum(float(s.get("weight", 1.0)) for s in signals)
        for s in signals:
            s["weight"] = round(float(s.get("weight", 1.0)) / total_w, 3)

        spec_data["signals"] = signals
        variant_id = str(uuid.uuid4())[:8]
        spec_data["name"] = f"{base_spec.name}_regime_{variant_id}"

        spec_yaml = yaml.dump(spec_data, sort_keys=False)
        spec_hash = self._hash_spec(spec_data)

        return {
            "id": f"hyp_reg_{variant_id}",
            "family": base_spec.family,
            "generator_type": "REGIME_VARIANT",
            "title": f"Regime-Aware Variant of {base_spec.name}",
            "description": f"Dynamically scales exposure of {base_spec.name} based on 4-quadrant market regime.",
            "base_spec_name": base_spec.name,
            "proposed_spec": spec_yaml,
            "spec_hash": spec_hash,
            "prior_score": Decimal("0.80"),
        }

    def generate_genetic_recombination(
        self,
        spec_parent_a: StrategySpec,
        spec_parent_b: StrategySpec,
    ) -> dict[str, Any]:
        """Cross over signals, weights, and policies from two elite parent strategies."""
        spec_a = copy.deepcopy(spec_parent_a.model_dump(mode="json"))
        spec_b = copy.deepcopy(spec_parent_b.model_dump(mode="json"))

        signals_a = list(spec_a.get("signals", []))
        signals_b = list(spec_b.get("signals", []))

        # Genetic crossover: pick half from parent A, half from parent B
        half_a = signals_a[: max(1, len(signals_a) // 2)]
        half_b = signals_b[: max(1, len(signals_b) // 2)]
        combined_signals = half_a + half_b

        # Normalize weights
        total_w = sum(float(s.get("weight", 1.0)) for s in combined_signals)
        for s in combined_signals:
            s["weight"] = round(float(s.get("weight", 1.0)) / total_w, 3)

        child_spec = copy.deepcopy(spec_a)
        child_spec["name"] = f"crossover_{spec_parent_a.family}_{str(uuid.uuid4())[:6]}"
        child_spec["signals"] = combined_signals
        child_spec["policy"] = copy.deepcopy(spec_b.get("policy", {}))

        spec_yaml = yaml.dump(child_spec, sort_keys=False)
        spec_hash = self._hash_spec(child_spec)

        return {
            "id": f"hyp_gen_{str(uuid.uuid4())[:8]}",
            "family": spec_parent_a.family,
            "generator_type": "GENETIC_RECOMBINATION",
            "title": f"Genetic Recombination ({spec_parent_a.name} × {spec_parent_b.name})",
            "description": f"Crossover of signal components between {spec_parent_a.name} and {spec_parent_b.name}.",
            "base_spec_name": f"{spec_parent_a.name}+{spec_parent_b.name}",
            "proposed_spec": spec_yaml,
            "spec_hash": spec_hash,
            "prior_score": Decimal("0.90"),
        }
