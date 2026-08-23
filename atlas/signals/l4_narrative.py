"""L4 Narrative & LLM Signal Providers with time-decay weighting and strict PIT discipline."""

from __future__ import annotations

import logging
import math

from atlas.core.context import MarketContext
from atlas.core.types import Signal, SignalLayer, Symbol
from atlas.signals.base import SignalProvider

logger = logging.getLogger("atlas.signals.l4_narrative")


class NewsSentimentSignalProvider(SignalProvider):
    """L4 Signal Provider: Exponentially time-decayed LLM news sentiment.

    Weights recent news by exponential half-life, relevance, and model confidence.
    """

    def __init__(
        self,
        id: str = "l4_news_sentiment",
        version: str = "1.0.0",
        lookback_hours: int = 48,
        half_life_hours: float = 18.0,
        min_relevance: float = 0.4,
        min_confidence: float = 0.5,
    ) -> None:
        self._id = id
        self._version = version
        self.lookback_hours = lookback_hours
        self.half_life_hours = half_life_hours
        self.min_relevance = min_relevance
        self.min_confidence = min_confidence

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L4_NARRATIVE

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        articles = ctx.news(symbol, lookback_hours=self.lookback_hours)
        if not articles:
            return None

        total_weight = 0.0
        weighted_sentiment = 0.0
        max_novelty = 0.0
        qualifying_count = 0
        latest_rationale = ""

        now_ts = ctx.now

        for item in articles:
            rel = item.relevance_score if item.relevance_score is not None else 0.75
            conf = item.confidence if item.confidence is not None else 0.8
            sentiment = item.sentiment_score if item.sentiment_score is not None else 0.0

            if rel < self.min_relevance or conf < self.min_confidence:
                continue

            dt_hours = max(0.0, (now_ts - item.ts).total_seconds() / 3600.0)
            time_decay = math.exp(-math.log(2) * (dt_hours / max(1.0, self.half_life_hours)))

            w = time_decay * rel * conf
            weighted_sentiment += sentiment * w
            total_weight += w
            qualifying_count += 1

            if item.novelty_score is not None and item.novelty_score > max_novelty:
                max_novelty = item.novelty_score

            if not latest_rationale and item.rationale:
                latest_rationale = item.rationale

        if total_weight <= 0.0 or qualifying_count == 0:
            return None

        composite_sentiment = weighted_sentiment / total_weight
        clamped_score = max(-1.0, min(1.0, composite_sentiment))

        # Higher confidence with multiple independent confirming sources & novelty
        confidence = min(0.95, 0.50 + 0.10 * math.log(qualifying_count + 1) + 0.15 * max_novelty)

        summary_rat = (
            latest_rationale
            if latest_rationale
            else f"Decayed sentiment from {qualifying_count} news articles across last {self.lookback_hours}h."
        )

        rationale = (
            f"L4 News Sentiment: score={clamped_score:+.2f} ({qualifying_count} articles, "
            f"novelty={max_novelty:.2f}, half-life={self.half_life_hours:.0f}h). {summary_rat}"
        )

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=float(clamped_score),
            confidence=float(confidence),
            rationale=rationale,
            features={
                "news_count": float(qualifying_count),
                "news_sentiment": float(clamped_score),
                "news_novelty": float(max_novelty),
            },
        )


class NarrativeMomentumSignalProvider(SignalProvider):
    """L4 Signal Provider: News volume surge & sentiment shift velocity."""

    def __init__(
        self,
        id: str = "l4_narrative_momentum",
        version: str = "1.0.0",
        fast_lookback_hours: int = 24,
        slow_lookback_hours: int = 72,
        min_relevance: float = 0.3,
    ) -> None:
        self._id = id
        self._version = version
        self.fast_lookback_hours = fast_lookback_hours
        self.slow_lookback_hours = slow_lookback_hours
        self.min_relevance = min_relevance

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L4_NARRATIVE

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        all_news = ctx.news(symbol, lookback_hours=self.slow_lookback_hours)
        if not all_news:
            return None

        now_ts = ctx.now
        fast_cutoff_sec = self.fast_lookback_hours * 3600.0

        fast_articles = []
        slow_articles = []

        for item in all_news:
            rel = item.relevance_score if item.relevance_score is not None else 0.7
            if rel < self.min_relevance:
                continue

            dt_sec = max(0.0, (now_ts - item.ts).total_seconds())
            if dt_sec <= fast_cutoff_sec:
                fast_articles.append(item)
            slow_articles.append(item)

        if not fast_articles:
            return None

        fast_sentiments = [
            a.sentiment_score for a in fast_articles if a.sentiment_score is not None
        ]
        slow_sentiments = [
            a.sentiment_score for a in slow_articles if a.sentiment_score is not None
        ]

        avg_fast_sent = sum(fast_sentiments) / len(fast_sentiments) if fast_sentiments else 0.0
        avg_slow_sent = sum(slow_sentiments) / len(slow_sentiments) if slow_sentiments else 0.0

        sentiment_delta = avg_fast_sent - avg_slow_sent

        # Volume acceleration: annualized ratio of fast vs slow coverage density
        fast_density = len(fast_articles) / float(self.fast_lookback_hours)
        slow_density = len(slow_articles) / float(self.slow_lookback_hours)
        volume_surge = fast_density / max(0.05, slow_density)

        # Composite narrative momentum: direction determined by fast sentiment * surge
        momentum_score = avg_fast_sent * min(2.0, volume_surge) + (0.5 * sentiment_delta)
        clamped_score = max(-1.0, min(1.0, momentum_score))

        confidence = min(0.90, 0.50 + 0.15 * min(3.0, volume_surge))

        rationale = (
            f"L4 Narrative Momentum: fast_sent={avg_fast_sent:+.2f}, slow_sent={avg_slow_sent:+.2f}, "
            f"delta={sentiment_delta:+.2f}, vol_surge={volume_surge:.2f}x ({len(fast_articles)} fast vs {len(slow_articles)} slow)."
        )

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=float(clamped_score),
            confidence=float(confidence),
            rationale=rationale,
            features={
                "narrative_fast_sent": float(avg_fast_sent),
                "narrative_slow_sent": float(avg_slow_sent),
                "narrative_delta": float(sentiment_delta),
                "narrative_vol_surge": float(volume_surge),
            },
        )


class ExecutiveCatalystSignalProvider(SignalProvider):
    """L4 Signal Provider: High-impact CEO / executive statements & product cycle breakthroughs.

    Focuses on transformative catalysts (product announcements, major contract wins, executive tone).
    """

    def __init__(
        self,
        id: str = "l4_executive_catalyst",
        version: str = "1.0.0",
        lookback_hours: int = 72,
        catalyst_weight: float = 1.5,
        min_relevance: float = 0.5,
    ) -> None:
        self._id = id
        self._version = version
        self.lookback_hours = lookback_hours
        self.catalyst_weight = catalyst_weight
        self.min_relevance = min_relevance

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L4_NARRATIVE

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        news_items = ctx.news(symbol, lookback_hours=self.lookback_hours)
        if not news_items:
            return None

        # Filter for high relevance items mentioning executive / product / strategic catalysts
        catalyst_keywords = (
            "ceo",
            "executive",
            "musk",
            "jensen",
            "product",
            "launch",
            "contract",
            "ai",
            "deal",
            "breakthrough",
            "guidance",
        )
        catalyst_scores: list[float] = []
        catalyst_rationales: list[str] = []

        for item in news_items:
            rel = item.relevance_score if item.relevance_score is not None else 0.7
            if rel < self.min_relevance:
                continue

            headline = (getattr(item, "headline", "") or getattr(item, "title", "") or "").lower()
            rationale = getattr(item, "rationale", "") or ""
            text_to_check = f"{headline} {rationale}".lower()

            is_catalyst = any(kw in text_to_check for kw in catalyst_keywords)
            score = item.sentiment_score if item.sentiment_score is not None else 0.0

            if is_catalyst:
                catalyst_scores.append(score * self.catalyst_weight)
                if rationale and not catalyst_rationales:
                    catalyst_rationales.append(rationale)
            else:
                catalyst_scores.append(score)

        if not catalyst_scores:
            return None

        avg_score = sum(catalyst_scores) / float(len(catalyst_scores))
        clamped_score = max(-1.0, min(1.0, avg_score))
        confidence = min(0.95, 0.55 + 0.10 * len(catalyst_scores))

        rat = (
            catalyst_rationales[0]
            if catalyst_rationales
            else f"Executive catalyst scoring across {len(catalyst_scores)} events."
        )

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=float(clamped_score),
            confidence=float(confidence),
            rationale=f"L4 Executive & Catalyst: score={clamped_score:+.2f}. {rat}",
            features={
                "catalyst_event_count": float(len(catalyst_scores)),
                "catalyst_composite_score": float(clamped_score),
            },
        )


class MacroGeopoliticalShockSignalProvider(SignalProvider):
    """L4 Signal Provider: Macroeconomic policy, tariffs, and geopolitical shock defense.

    Scales down exposure or flags defensive rotation during macro policy turbulence.
    """

    def __init__(
        self,
        id: str = "l4_macro_shock",
        version: str = "1.0.0",
        lookback_hours: int = 48,
        tariff_sensitivity: float = 1.2,
    ) -> None:
        self._id = id
        self._version = version
        self.lookback_hours = lookback_hours
        self.tariff_sensitivity = tariff_sensitivity

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L4_NARRATIVE

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        # Check macro news for broad market ETF or individual symbol
        macro_news = ctx.news(Symbol("SPY"), lookback_hours=self.lookback_hours) or ctx.news(
            symbol, lookback_hours=self.lookback_hours
        )
        if not macro_news:
            return None

        macro_keywords = (
            "tariff",
            "trade war",
            "sanction",
            "fed",
            "inflation",
            "rate hike",
            "recession",
            "executive order",
            "trump",
        )
        shock_scores: list[float] = []

        for item in macro_news:
            headline = (getattr(item, "headline", "") or getattr(item, "title", "") or "").lower()
            rationale = (getattr(item, "rationale", "") or "").lower()
            if any(kw in f"{headline} {rationale}" for kw in macro_keywords):
                score = item.sentiment_score if item.sentiment_score is not None else 0.0
                shock_scores.append(score * self.tariff_sensitivity)

        if not shock_scores:
            return None

        avg_shock = sum(shock_scores) / float(len(shock_scores))
        clamped_score = max(-1.0, min(1.0, avg_shock))
        confidence = min(0.90, 0.60 + 0.05 * len(shock_scores))

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=float(clamped_score),
            confidence=float(confidence),
            rationale=f"L4 Macro/Geopolitical Shock: score={clamped_score:+.2f} ({len(shock_scores)} macro shock events)",
            features={
                "macro_shock_events": float(len(shock_scores)),
                "macro_shock_score": float(clamped_score),
            },
        )
