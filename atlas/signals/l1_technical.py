"""L1 Technical Signal Providers implementing technical indicators."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from atlas.core.context import MarketContext
from atlas.core.types import Signal, SignalLayer, Symbol
from atlas.signals.indicators import (
    compute_52w_position,
    compute_bollinger_bands,
    compute_ema,
    compute_macd,
    compute_momentum_roc,
    compute_rsi,
    compute_sma,
    compute_volume_zscore,
)


@dataclass(frozen=True, slots=True)
class TrendFilterSignalProvider:
    """Trend filter signal based on SMA or EMA moving average."""

    id: str = "l1_trend_filter"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    ma_period: int = 200
    ma_type: str = "sma"  # "sma" or "ema"

    def warmup_bars(self) -> int:
        if self.ma_type.lower() == "ema":
            return max(self.ma_period + 50, self.ma_period * 2)
        return self.ma_period + 5

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars(), adjusted=True)
        if df.is_empty() or len(df) < self.ma_period:
            return None

        closes = df["close"].to_numpy().astype(np.float64)
        ma_val = (
            compute_ema(closes, self.ma_period)
            if self.ma_type.lower() == "ema"
            else compute_sma(closes, self.ma_period)
        )
        if ma_val is None or ma_val <= 0.0:
            return None

        current_close = float(closes[-1])
        diff_pct = (current_close - ma_val) / ma_val
        # Score +1.0 if above MA, -1.0 if below MA
        score = 1.0 if current_close >= ma_val else -1.0
        confidence = float(min(1.0, max(0.3, abs(diff_pct) * 10.0 + 0.3)))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=f"Price {current_close:.2f} vs {self.ma_type.upper()}({self.ma_period}) {ma_val:.2f} ({diff_pct:+.2%})",
            features={
                "ma": ma_val,
                "close": current_close,
                "diff_pct": diff_pct,
            },
        )


@dataclass(frozen=True, slots=True)
class MomentumSignalProvider:
    """Cross-sectional or time-series momentum (ROC) signal with skip period."""

    id: str = "l1_momentum"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    lookback: int = 252
    skip: int = 21

    def warmup_bars(self) -> int:
        return self.lookback + 10

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars(), adjusted=True)
        if df.is_empty() or len(df) < self.lookback + 1:
            return None

        closes = df["close"].to_numpy().astype(np.float64)
        roc = compute_momentum_roc(closes, lookback=self.lookback, skip=self.skip)
        if roc is None:
            return None

        # Map ROC to score [-1.0 .. 1.0] using hyperbolic tangent scaling (e.g. 30% roc -> ~0.8)
        score = float(np.tanh(roc * 3.0))
        confidence = float(min(1.0, max(0.4, abs(score))))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=f"Momentum({self.lookback},{self.skip}) = {roc:+.2%}",
            features={
                "roc": roc,
            },
        )


@dataclass(frozen=True, slots=True)
class RsiSignalProvider:
    """RSI mean-reversion or momentum indicator."""

    id: str = "l1_rsi"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    period: int = 2
    oversold: float = 10.0
    overbought: float = 90.0
    mode: str = "mean_reversion"  # "mean_reversion" or "trend"

    def warmup_bars(self) -> int:
        return self.period + 30

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars(), adjusted=True)
        if df.is_empty() or len(df) < self.period + 5:
            return None

        closes = df["close"].to_numpy().astype(np.float64)
        rsi = compute_rsi(closes, period=self.period)
        if rsi is None:
            return None

        score: float
        confidence: float
        if self.mode == "mean_reversion":
            # In mean reversion, RSI < oversold is strongly bullish (buy the dip)
            if rsi <= self.oversold:
                score = 1.0
                confidence = float(1.0 - (rsi / (self.oversold + 1e-5)) * 0.2)
            elif rsi >= self.overbought:
                score = -1.0
                confidence = float(
                    0.8 + ((rsi - self.overbought) / (100.0 - self.overbought + 1e-5)) * 0.2
                )
            else:
                # Linear interpolation in neutral range
                score = float((50.0 - rsi) / 50.0)
                confidence = 0.3
        else:
            # Trend mode: high RSI is bullish momentum
            score = float((rsi - 50.0) / 50.0)
            confidence = float(min(1.0, max(0.3, abs(score))))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=max(-1.0, min(1.0, score)),
            confidence=max(0.0, min(1.0, confidence)),
            rationale=f"RSI({self.period}) = {rsi:.1f} (mode={self.mode})",
            features={
                "rsi": rsi,
            },
        )


@dataclass(frozen=True, slots=True)
class MacdSignalProvider:
    """MACD signal provider tracking momentum convergence/divergence."""

    id: str = "l1_macd"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9

    def warmup_bars(self) -> int:
        return self.slow_period + self.signal_period + 20

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars(), adjusted=True)
        if df.is_empty() or len(df) < self.slow_period + self.signal_period:
            return None

        closes = df["close"].to_numpy().astype(np.float64)
        macd_res = compute_macd(
            closes,
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            signal_period=self.signal_period,
        )
        if macd_res is None:
            return None

        macd_line, sig_line, hist = macd_res
        current_close = float(closes[-1])
        # Normalized histogram by price with lower bound clamping to prevent penny stock explosion
        denom = max(1.0, current_close)
        norm_hist = hist / denom if current_close > 0 else 0.0
        score = float(np.tanh(norm_hist * 100.0))
        confidence = float(min(1.0, max(0.3, abs(score))))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=f"MACD line={macd_line:.2f}, signal={sig_line:.2f}, hist={hist:.2f}",
            features={
                "macd_line": macd_line,
                "signal_line": sig_line,
                "macd_hist": hist,
            },
        )


@dataclass(frozen=True, slots=True)
class BollingerSignalProvider:
    """Bollinger Bands %B signal provider."""

    id: str = "l1_bollinger"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    period: int = 20
    num_std: float = 2.0
    mode: str = "mean_reversion"  # "mean_reversion" or "breakout"

    def warmup_bars(self) -> int:
        return self.period + 10

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars(), adjusted=True)
        if df.is_empty() or len(df) < self.period:
            return None

        closes = df["close"].to_numpy().astype(np.float64)
        bb_res = compute_bollinger_bands(closes, period=self.period, num_std=self.num_std)
        if bb_res is None:
            return None

        middle, upper, lower, percent_b = bb_res
        if self.mode == "mean_reversion":
            # percent_b <= 0 (below lower band) -> bullish rebound (+1.0)
            # percent_b >= 1 (above upper band) -> bearish pullback (-1.0)
            score = float(1.0 - 2.0 * percent_b)
        else:
            # Breakout mode: above upper band is bullish continuation
            score = float(2.0 * percent_b - 1.0)

        score = max(-1.0, min(1.0, score))
        confidence = float(min(1.0, max(0.3, abs(score))))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=f"Bollinger %B = {percent_b:.2f} (mid={middle:.2f}, up={upper:.2f}, lo={lower:.2f})",
            features={
                "percent_b": percent_b,
                "bb_middle": middle,
                "bb_upper": upper,
                "bb_lower": lower,
            },
        )


@dataclass(frozen=True, slots=True)
class FiftyTwoWeekSignalProvider:
    """52-week position signal provider."""

    id: str = "l1_52w_position"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    period: int = 252

    def warmup_bars(self) -> int:
        return self.period + 10

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars(), adjusted=True)
        if df.is_empty() or len(df) < self.period:
            return None

        closes = df["close"].to_numpy().astype(np.float64)
        highs = df["high"].to_numpy().astype(np.float64) if "high" in df.columns else None
        lows = df["low"].to_numpy().astype(np.float64) if "low" in df.columns else None
        pos = compute_52w_position(closes, period=self.period, highs=highs, lows=lows)
        if pos is None:
            return None

        # pos in [0, 1] -> score in [-1, 1]
        score = float(2.0 * pos - 1.0)
        confidence = float(min(1.0, max(0.4, abs(score))))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=f"52w-Position = {pos:.2%}",
            features={
                "52w_position": pos,
            },
        )


@dataclass(frozen=True, slots=True)
class VolumeZScoreSignalProvider:
    """Volume z-score signal provider."""

    id: str = "l1_volume_zscore"
    version: str = "1.0.0"
    layer: SignalLayer = SignalLayer.L1_TECHNICAL
    period: int = 20

    def warmup_bars(self) -> int:
        return self.period + 10

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        df = ctx.bars(symbol, lookback=self.warmup_bars())
        if df.is_empty() or len(df) < self.period:
            return None

        volumes = df["volume"].to_numpy().astype(np.float64)
        z = compute_volume_zscore(volumes, period=self.period)
        if z is None:
            return None

        score = float(np.tanh(z / 2.0))
        confidence = float(min(1.0, max(0.3, abs(score))))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=score,
            confidence=confidence,
            rationale=f"Volume Z-score = {z:.2f}",
            features={
                "volume_zscore": z,
            },
        )
