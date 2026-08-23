"""L2 Statistical and Machine Learning Signal Providers."""

from __future__ import annotations

from atlas.core.context import MarketContext
from atlas.core.types import Signal, SignalLayer, Symbol
from atlas.ml.models import ModelArtifact
from atlas.ml.registry import ModelRegistry
from atlas.signals.base import SignalProvider
from atlas.signals.features.extractor import FeatureEngine
from atlas.signals.regime import MarketQuadrant, RegimeDetector


class CrossSectionalMomentumProvider(SignalProvider):
    """L2 Alpha Signal Provider based on cross-sectional 12m-1m momentum ranking."""

    def __init__(
        self,
        id: str = "l2_cs_momentum",
        version: str = "1.0.0",
        skip_bars: int = 21,
        lookback_bars: int = 252,
    ) -> None:
        self._id = id
        self._version = version
        self._skip_bars = skip_bars
        self._lookback_bars = lookback_bars
        self._feat_engine = FeatureEngine()

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L2_STATISTICAL

    def warmup_bars(self) -> int:
        return self._lookback_bars + 20

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars())
        if df.is_empty() or len(df) < self._lookback_bars:
            return None

        # Cross-sectional momentum evaluation across active universe
        universe = ctx.universe()
        if not universe:
            universe = [symbol]

        cs_ranks = self._feat_engine.cs_ranker.evaluate_universe_features(ctx, universe)
        sym_ranks = cs_ranks.get(symbol, {})
        rank_val = sym_ranks.get("cs_rank_momentum_12m_1m", 0.5)

        # Map [0.0 .. 1.0] to [-1.0 .. +1.0]
        score = (rank_val - 0.5) * 2.0
        confidence = 0.5 + abs(rank_val - 0.5)  # [0.5 .. 1.0]

        pct_formatted = rank_val * 100.0
        rationale = (
            f"L2 CS Momentum: {symbol} ranks at {pct_formatted:.1f}th percentile across universe "
            f"(12m-1m return with 21d skip)."
        )

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=max(-1.0, min(1.0, score)),
            confidence=max(0.0, min(1.0, confidence)),
            rationale=rationale,
            features={"cs_rank": rank_val, "universe_size": float(len(universe))},
        )


class MarketRegimeSignalProvider(SignalProvider):
    """L2 Context & Alpha Signal Provider based on 4-Quadrant Market Regime Detection."""

    def __init__(
        self,
        id: str = "l2_market_regime",
        version: str = "1.0.0",
        benchmark: str = "SPY",
    ) -> None:
        self._id = id
        self._version = version
        self._benchmark = Symbol(benchmark)
        self._detector = RegimeDetector(default_benchmark=benchmark)

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L2_STATISTICAL

    def warmup_bars(self) -> int:
        return 260

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        regime = self._detector.classify(ctx, benchmark=self._benchmark)

        score_map = {
            MarketQuadrant.BULL_LOW_VOL: 1.0,
            MarketQuadrant.BULL_HIGH_VOL: 0.35,
            MarketQuadrant.SIDEWAYS_NORMAL: 0.0,
            MarketQuadrant.BEAR_LOW_VOL: -0.5,
            MarketQuadrant.BEAR_HIGH_VOL: -1.0,
        }
        score = score_map.get(regime.quadrant, 0.0)

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=regime.confidence,
            rationale=f"Regime {regime.quadrant.value}: {regime.rationale}",
            features={
                "realized_vol_21d": regime.realized_vol_21d,
                "breadth_pct_50d": regime.breadth_pct_50d,
                "trend_score": regime.trend_score,
                "vol_score": regime.vol_score,
            },
        )


class LightGBMSignalProvider(SignalProvider):
    """L2 Machine Learning Signal Provider executing trained LightGBM models with SHAP explanations."""

    def __init__(
        self,
        id: str = "l2_lightgbm",
        version: str = "1.0.0",
        model_id: str = "lgbm_dir_5d_v1",
        model_version: str = "1.0.0",
        registry: ModelRegistry | None = None,
        artifact: ModelArtifact | None = None,
    ) -> None:
        self._id = id
        self._version = version
        self._model_id = model_id
        self._model_version = model_version
        self._registry = registry or ModelRegistry()
        self._artifact = artifact
        self._feat_engine = FeatureEngine()

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L2_STATISTICAL

    def warmup_bars(self) -> int:
        return 270

    def _get_artifact(self) -> ModelArtifact | None:
        if self._artifact is not None:
            return self._artifact
        try:
            self._artifact = self._registry.load(self._model_id, self._model_version)
            return self._artifact
        except Exception:
            return None

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars())
        if df.is_empty() or len(df) < 252:
            return None

        artifact = self._get_artifact()
        if artifact is None:
            # Fallback statistical scoring if model is not yet trained/registered
            stat_feats = self._feat_engine.extract_single_symbol_pit(ctx, symbol)
            mom = stat_feats.get("return_21d", 0.0)
            score = float(max(-1.0, min(1.0, mom * 10.0)))
            return Signal(
                provider=self.id,
                layer=self.layer,
                symbol=symbol,
                ts=ctx.now,
                score=score,
                confidence=0.5,
                rationale=f"Statistical fallback score {score:.2f} (model {self._model_id} pending training).",
                features=stat_feats,
            )

        features = self._feat_engine.extract_single_symbol_pit(ctx, symbol)
        score, explanation = artifact.predict(features)
        confidence = 0.5 + abs(score) * 0.45

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=explanation.rationale,
            features=features,
        )
