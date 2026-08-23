"""Market Regime Detection and 4-Quadrant Classification Engine."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from atlas.core.context import MarketContext
from atlas.core.types import Symbol
from atlas.signals.features.breadth import MarketBreadthCalculator


class TrendRegime(StrEnum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"


class VolatilityRegime(StrEnum):
    LOW_VOL = "LOW_VOL"
    NORMAL_VOL = "NORMAL_VOL"
    HIGH_VOL = "HIGH_VOL"


class MarketQuadrant(StrEnum):
    BULL_LOW_VOL = "BULL_LOW_VOL"  # Expansion / steady trend (optimal equity conditions)
    BULL_HIGH_VOL = "BULL_HIGH_VOL"  # Late-cycle / volatile rally (cautious trend)
    BEAR_HIGH_VOL = "BEAR_HIGH_VOL"  # Market crash / panic / rapid liquidation
    BEAR_LOW_VOL = "BEAR_LOW_VOL"  # Slow grind down / prolonged stagnation
    SIDEWAYS_NORMAL = "SIDEWAYS_NORMAL"  # Consolidation / rangebound trading


@dataclass(frozen=True)
class RegimeState:
    """Snapshot of classified market regime conditions."""

    trend: TrendRegime
    volatility: VolatilityRegime
    quadrant: MarketQuadrant
    trend_score: float  # [-1.0 (strongly bearish) .. +1.0 (strongly bullish)]
    vol_score: float  # [0.0 (extremely low vol) .. 1.0 (extreme high vol)]
    confidence: float  # [0.0 .. 1.0]
    breadth_pct_50d: float  # Percentage of universe above 50-day SMA
    breadth_pct_200d: float  # Percentage of universe above 200-day SMA
    realized_vol_21d: float  # Annualized 21d realized vol of benchmark
    benchmark_symbol: Symbol
    rationale: str  # Plain-English summary of regime state


class RegimeDetector:
    """Classifies prevailing market regime using benchmark price action, volatility, and universe breadth."""

    def __init__(
        self,
        default_benchmark: str = "SPY",
        vol_low_threshold: float = 0.12,  # Annualized vol < 12% is low vol
        vol_high_threshold: float = 0.22,  # Annualized vol > 22% is high vol
    ) -> None:
        self.default_benchmark = Symbol(default_benchmark)
        self.vol_low_threshold = vol_low_threshold
        self.vol_high_threshold = vol_high_threshold
        self._breadth_calc = MarketBreadthCalculator()

    def classify(
        self,
        ctx: MarketContext,
        benchmark: Symbol | None = None,
        universe: Sequence[Symbol] | None = None,
    ) -> RegimeState:
        """Classify market regime strictly at or before ctx.now."""
        bench = benchmark or self.default_benchmark
        df = ctx.bars(bench, lookback=260)

        if df.is_empty() or len(df) < 50:
            # Insufficient warmup - return neutral sideways state
            return RegimeState(
                trend=TrendRegime.SIDEWAYS,
                volatility=VolatilityRegime.NORMAL_VOL,
                quadrant=MarketQuadrant.SIDEWAYS_NORMAL,
                trend_score=0.0,
                vol_score=0.5,
                confidence=0.3,
                breadth_pct_50d=0.5,
                breadth_pct_200d=0.5,
                realized_vol_21d=0.15,
                benchmark_symbol=bench,
                rationale="Insufficient historical data for benchmark; defaulting to neutral sideways regime.",
            )

        closes = df["close"].to_numpy().astype(float)
        n = len(closes)
        current_price = closes[-1]

        # 1. Moving Averages & Trend
        sma50 = float(np.mean(closes[-50:]))
        sma200 = float(np.mean(closes[-200:])) if n >= 200 else sma50

        # Trend score components
        above_50 = (current_price - sma50) / sma50 if sma50 > 0 else 0.0
        above_200 = (current_price - sma200) / sma200 if sma200 > 0 else 0.0
        ma_cross = (sma50 - sma200) / sma200 if sma200 > 0 else 0.0

        # Normalized trend score [-1.0 .. +1.0]
        raw_trend = (above_50 * 0.4) + (above_200 * 0.4) + (ma_cross * 0.2)
        trend_score = max(-1.0, min(1.0, raw_trend * 10.0))

        if trend_score > 0.15:
            trend = TrendRegime.BULL
        elif trend_score < -0.15:
            trend = TrendRegime.BEAR
        else:
            trend = TrendRegime.SIDEWAYS

        # 2. Volatility Analysis
        ret1 = [
            (closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, n) if closes[i - 1] > 0
        ]
        recent_rets = ret1[-21:] if len(ret1) >= 21 else ret1
        vol_21d = (
            float(np.std(recent_rets, ddof=1)) * np.sqrt(252.0) if len(recent_rets) > 3 else 0.15
        )

        if vol_21d < self.vol_low_threshold:
            vol_regime = VolatilityRegime.LOW_VOL
            vol_score = max(0.0, vol_21d / self.vol_low_threshold * 0.33)
        elif vol_21d > self.vol_high_threshold:
            vol_regime = VolatilityRegime.HIGH_VOL
            vol_score = min(1.0, 0.67 + (vol_21d - self.vol_high_threshold) / 0.20 * 0.33)
        else:
            vol_regime = VolatilityRegime.NORMAL_VOL
            span = self.vol_high_threshold - self.vol_low_threshold
            vol_score = 0.33 + ((vol_21d - self.vol_low_threshold) / span) * 0.34

        # 3. Market Breadth (if universe provided)
        breadth_pct_50d = 0.5
        breadth_pct_200d = 0.5
        if universe:
            breadth_dict = self._breadth_calc.compute_breadth(ctx, universe)
            breadth_pct_50d = breadth_dict.get("breadth_pct_above_50d", 0.5)
            breadth_pct_200d = breadth_dict.get("breadth_pct_above_200d", 0.5)

        # 4. Quadrant Mapping
        if trend == TrendRegime.BULL and vol_regime in (
            VolatilityRegime.LOW_VOL,
            VolatilityRegime.NORMAL_VOL,
        ):
            quadrant = MarketQuadrant.BULL_LOW_VOL
            rationale = (
                f"Bullish expansion: {bench} price is above moving averages with healthy low/moderate "
                f"realized volatility ({vol_21d:.1%}). Favorable for trend-following and momentum."
            )
        elif trend == TrendRegime.BULL and vol_regime == VolatilityRegime.HIGH_VOL:
            quadrant = MarketQuadrant.BULL_HIGH_VOL
            rationale = (
                f"Volatile bull rally: {bench} is trending upward but experiencing elevated volatility "
                f"({vol_21d:.1%}). Requires tighter stops and reduced position sizes."
            )
        elif trend == TrendRegime.BEAR and vol_regime == VolatilityRegime.HIGH_VOL:
            quadrant = MarketQuadrant.BEAR_HIGH_VOL
            rationale = (
                f"Market sell-off / high stress: {bench} below moving averages with severe volatility "
                f"({vol_21d:.1%}). Risk of cascading liquidations. Capital preservation active."
            )
        elif trend == TrendRegime.BEAR and vol_regime in (
            VolatilityRegime.LOW_VOL,
            VolatilityRegime.NORMAL_VOL,
        ):
            quadrant = MarketQuadrant.BEAR_LOW_VOL
            rationale = (
                f"Grinding downtrend: {bench} below long-term moving averages in quiet, persistent decline "
                f"({vol_21d:.1%}). Avoid long exposure."
            )
        else:
            quadrant = MarketQuadrant.SIDEWAYS_NORMAL
            rationale = (
                f"Rangebound consolidation: {bench} fluctuating near moving averages with normal volatility "
                f"({vol_21d:.1%}). Favorable for mean-reversion strategies."
            )

        # Confidence metric based on alignment
        confidence = 0.5 + abs(trend_score) * 0.3 + abs(vol_score - 0.5) * 0.2
        confidence = max(0.2, min(0.95, confidence))

        return RegimeState(
            trend=trend,
            volatility=vol_regime,
            quadrant=quadrant,
            trend_score=trend_score,
            vol_score=vol_score,
            confidence=confidence,
            breadth_pct_50d=breadth_pct_50d,
            breadth_pct_200d=breadth_pct_200d,
            realized_vol_21d=vol_21d,
            benchmark_symbol=bench,
            rationale=rationale,
        )
