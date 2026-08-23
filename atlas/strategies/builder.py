"""Builder utility to instantiate strategy components from StrategySpec."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
from atlas.signals.l2_statistical import (
    CrossSectionalMomentumProvider,
    LightGBMSignalProvider,
    MarketRegimeSignalProvider,
)
from atlas.signals.l3_fundamental import (
    EarningsSurpriseSignalProvider,
    ValuationQualitySignalProvider,
)
from atlas.signals.l4_narrative import (
    ExecutiveCatalystSignalProvider,
    MacroGeopoliticalShockSignalProvider,
    NarrativeMomentumSignalProvider,
    NewsSentimentSignalProvider,
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
    elif name in (
        "l2_cs_momentum",
        "cs_momentum",
        "cross_sectional_momentum",
        "l2_cross_sectional_momentum",
    ):
        return CrossSectionalMomentumProvider(
            id=provider_name,
            skip_bars=int(params.get("skip_bars", 21)),
            lookback_bars=int(params.get("lookback_bars", 252)),
        )
    elif name in (
        "l2_market_regime",
        "market_regime",
        "regime_detector",
        "l2_regime_detector",
    ):
        return MarketRegimeSignalProvider(
            id=provider_name,
            benchmark=str(params.get("benchmark", "SPY")),
        )
    elif name in ("l2_lightgbm", "lightgbm", "lgbm_model"):
        return LightGBMSignalProvider(
            id=provider_name,
            model_id=str(params.get("model_id", "lgbm_dir_5d_v1")),
            model_version=str(params.get("model_version", "1.0.0")),
        )
    elif name in (
        "l3_val_quality",
        "val_quality",
        "fundamental_quality",
        "garp",
        "l3_composite_fundamental",
        "composite_fundamental",
    ):
        return ValuationQualitySignalProvider(
            id=provider_name,
            min_roic=float(params.get("min_roic", 0.08)),
            max_accrual_ratio=float(params.get("max_accrual_ratio", 0.05)),
            min_fcf_yield=float(params.get("min_fcf_yield", 0.02)),
            max_ev_ebitda=float(params.get("max_ev_ebitda", 25.0)),
        )
    elif name in ("l3_earnings_surprise", "earnings_surprise", "pead"):
        return EarningsSurpriseSignalProvider(
            id=provider_name,
            lookback_days=int(params.get("lookback_days", 30)),
        )
    elif name in ("l4_news_sentiment", "news_sentiment", "llm_sentiment"):
        return NewsSentimentSignalProvider(
            id=provider_name,
            lookback_hours=int(params.get("lookback_hours", 48)),
            half_life_hours=float(params.get("half_life_hours", 18.0)),
            min_relevance=float(params.get("min_relevance", 0.4)),
            min_confidence=float(params.get("min_confidence", 0.5)),
        )
    elif name in ("l4_narrative_momentum", "narrative_momentum", "news_velocity"):
        return NarrativeMomentumSignalProvider(
            id=provider_name,
            fast_lookback_hours=int(params.get("fast_lookback_hours", 24)),
            slow_lookback_hours=int(params.get("slow_lookback_hours", 72)),
            min_relevance=float(params.get("min_relevance", 0.3)),
        )
    elif name in (
        "l4_executive_catalyst",
        "executive_catalyst",
        "ceo_catalyst",
        "product_catalyst",
    ):
        return ExecutiveCatalystSignalProvider(
            id=provider_name,
            lookback_hours=int(params.get("lookback_hours", 72)),
            catalyst_weight=float(params.get("catalyst_weight", 1.5)),
            min_relevance=float(params.get("min_relevance", 0.5)),
        )
    elif name in ("l4_macro_shock", "macro_shock", "geopolitical_shock", "tariff_filter"):
        return MacroGeopoliticalShockSignalProvider(
            id=provider_name,
            lookback_hours=int(params.get("lookback_hours", 48)),
            tariff_sensitivity=float(params.get("tariff_sensitivity", 1.2)),
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
    elif pol_type in (
        "threshold_long_only",
        "threshold",
        "threshold_long_short",
        "threshold_short",
    ):
        return ThresholdLongOnlyPolicy(
            enter_threshold=spec.policy.enter_threshold,
            exit_threshold=spec.policy.exit_threshold,
            max_positions=spec.policy.n,
            bucket=spec.bucket,
            max_position_pct=Decimal(str(spec.policy.max_position_pct)),
            allow_short=bool(
                spec.policy.allow_short or pol_type in ("threshold_long_short", "threshold_short")
            ),
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
    from atlas.backtest.costs import DefaultCostModelV1

    return DefaultCostModelV1(
        k=spec.costs.k,
        broker_commission_type=spec.costs.broker,
    )
