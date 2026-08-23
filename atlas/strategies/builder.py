"""Builder utility to instantiate strategy components from StrategySpec."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from atlas.backtest.costs import DefaultCostModelV1
from atlas.portfolio.policies import (
    PositionPolicy,
    TargetWeightPolicy,
    ThresholdLongOnlyPolicy,
    TopNLongOnlyPolicy,
)
from atlas.signals.aggregator import WeightedConfidenceAggregator
from atlas.signals.base import SignalProvider
from atlas.signals.l1_technical import (
    BollingerSignalProvider,
    FiftyTwoWeekSignalProvider,
    MacdSignalProvider,
    MomentumSignalProvider,
    RsiSignalProvider,
    TrendFilterSignalProvider,
    VolumeZScoreSignalProvider,
)
from atlas.strategies.spec import StrategySpec


def build_signal_provider(provider_name: str, params: dict[str, Any]) -> SignalProvider:
    """Instantiate a signal provider from name and parameters."""
    name = provider_name.lower().strip()
    if name in ("l1_trend_filter", "trend_filter", "sma_trend"):
        return TrendFilterSignalProvider(
            id=provider_name,
            ma_period=int(params.get("ma_period", 200)),
            ma_type=str(params.get("ma_type", "sma")),
        )
    elif name in ("l1_momentum", "momentum", "roc"):
        return MomentumSignalProvider(
            id=provider_name,
            lookback=int(params.get("lookback", 252)),
            skip=int(params.get("skip", 21)),
        )
    elif name in ("l1_rsi", "rsi"):
        return RsiSignalProvider(
            id=provider_name,
            period=int(params.get("period", 2)),
            oversold=float(params.get("oversold", 10.0)),
            overbought=float(params.get("overbought", 90.0)),
            mode=str(params.get("mode", "mean_reversion")),
        )
    elif name in ("l1_macd", "macd"):
        return MacdSignalProvider(
            id=provider_name,
            fast_period=int(params.get("fast_period", 12)),
            slow_period=int(params.get("slow_period", 26)),
            signal_period=int(params.get("signal_period", 9)),
        )
    elif name in ("l1_bollinger", "bollinger"):
        return BollingerSignalProvider(
            id=provider_name,
            period=int(params.get("period", 20)),
            num_std=float(params.get("num_std", 2.0)),
            mode=str(params.get("mode", "mean_reversion")),
        )
    elif name in ("l1_52w_position", "52w_position"):
        return FiftyTwoWeekSignalProvider(
            id=provider_name,
            period=int(params.get("period", 252)),
        )
    elif name in ("l1_volume_zscore", "volume_zscore"):
        return VolumeZScoreSignalProvider(
            id=provider_name,
            period=int(params.get("period", 20)),
        )
    else:
        raise ValueError(f"Unknown signal provider: {provider_name}")


def build_aggregator(spec: StrategySpec) -> WeightedConfidenceAggregator:
    """Build WeightedConfidenceAggregator from strategy spec."""
    weights = {sig.provider: sig.weight for sig in spec.signals}
    return WeightedConfidenceAggregator(
        min_confidence=spec.aggregator.min_confidence,
        weights=weights,
    )


def build_position_policy(spec: StrategySpec) -> PositionPolicy:
    """Build PositionPolicy from strategy spec."""
    pol_type = spec.policy.type.lower()
    if pol_type in ("top_n_long_only", "top_n"):
        return TopNLongOnlyPolicy(
            n=spec.policy.n,
            min_score=spec.policy.min_score,
            weight_by=spec.policy.weight_by,
            max_position_pct=Decimal(str(spec.policy.max_position_pct)),
            bucket=spec.bucket,
        )
    elif pol_type in ("threshold_long_only", "threshold"):
        return ThresholdLongOnlyPolicy(
            enter_threshold=spec.policy.enter_threshold,
            exit_threshold=spec.policy.exit_threshold,
            max_positions=spec.policy.n,
            bucket=spec.bucket,
            max_position_pct=Decimal(str(spec.policy.max_position_pct)),
        )
    elif pol_type in ("target_weight", "weight"):
        return TargetWeightPolicy(
            bucket=spec.bucket,
            max_position_pct=Decimal(str(spec.policy.max_position_pct)),
            min_score=spec.policy.min_score,
        )
    else:
        raise ValueError(f"Unknown position policy type: {spec.policy.type}")


def build_cost_model(spec: StrategySpec) -> DefaultCostModelV1:
    """Build DefaultCostModelV1 from strategy spec."""
    return DefaultCostModelV1(
        k=spec.costs.k,
        broker_commission_type=spec.costs.broker,
    )
