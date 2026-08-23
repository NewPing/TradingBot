"""Signal aggregation engine implementing confidence-weighted combination."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from atlas.core.types import Signal, SignalLayer, Symbol


@dataclass(frozen=True, slots=True)
class WeightedConfidenceAggregator:
    """Aggregates multiple signals using confidence and user-specified provider weights.

    Formula:
        composite_score = Σ(w_i * score_i * conf_i) / Σ(w_i * conf_i)
        composite_conf  = mean(conf_i) or min(1.0, Σ(w_i * conf_i) / Σ(w_i))

    If total effective confidence is below min_confidence, abstention occurs.
    """

    min_confidence: float = 0.3
    weights: dict[str, float] = field(default_factory=dict)

    def combine(self, signals: list[Signal], current_ts: datetime, symbol: Symbol) -> Signal | None:
        """Combine multiple signals for a single symbol into a single composite signal."""
        if not signals:
            return None

        numerator = 0.0
        denominator = 0.0
        total_weight = 0.0
        combined_features: dict[str, float] = {}
        highest_layer = SignalLayer.L1_TECHNICAL

        for s in signals:
            w = self.weights.get(s.provider, 1.0)
            if w <= 0.0:
                continue

            eff_conf = w * s.confidence
            numerator += eff_conf * s.score
            denominator += eff_conf
            total_weight += w

            # Merge features with provider prefix
            for k, v in s.features.items():
                combined_features[f"{s.provider}_{k}"] = v

            # Track highest layer
            if s.layer > highest_layer:
                highest_layer = s.layer

        if denominator <= 0.0 or total_weight <= 0.0:
            return None

        avg_confidence = denominator / total_weight
        if avg_confidence < self.min_confidence:
            return None

        raw_score = numerator / denominator
        clamped_score = max(-1.0, min(1.0, raw_score))
        clamped_confidence = max(0.0, min(1.0, avg_confidence))

        rationale = f"Composite score {clamped_score:+.2f} (conf {clamped_confidence:.2f}) from {len(signals)} signals"

        return Signal(
            provider="aggregator",
            layer=highest_layer,
            symbol=symbol,
            ts=current_ts,
            score=clamped_score,
            confidence=clamped_confidence,
            rationale=rationale,
            features=combined_features,
        )
