"""L3 Fundamental and Valuation Signal Providers with Point-in-Time discipline."""

from __future__ import annotations

import logging

from atlas.core.context import MarketContext
from atlas.core.types import Signal, SignalLayer, Symbol
from atlas.signals.base import SignalProvider
from atlas.signals.features.fundamental import (
    FundamentalFeatureExtractor,
)

logger = logging.getLogger("atlas.signals.l3_fundamental")


class ValuationQualitySignalProvider(SignalProvider):
    """L3 Alpha Signal Provider: Quality-at-a-Reasonable-Price (GARP).

    Combines ROIC, Free Cash Flow Yield, Sloan Accrual Quality, and EV/EBITDA.
    """

    def __init__(
        self,
        id: str = "l3_val_quality",
        version: str = "1.0.0",
        min_roic: float = 0.08,
        max_accrual_ratio: float = 0.05,
        min_fcf_yield: float = 0.02,
        max_ev_ebitda: float = 25.0,
    ) -> None:
        self._id = id
        self._version = version
        self.min_roic = min_roic
        self.max_accrual_ratio = max_accrual_ratio
        self.min_fcf_yield = min_fcf_yield
        self.max_ev_ebitda = max_ev_ebitda
        self.extractor = FundamentalFeatureExtractor()

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L3_FUNDAMENTAL

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        snapshot = ctx.fundamentals(symbol)
        if snapshot is None:
            return None

        feats = self.extractor.compute_features_from_snapshot(snapshot)

        roic = feats["fund_roic"]
        accrual = feats["fund_accrual_ratio"]
        fcf_yield = feats["fund_fcf_yield"]
        ev_ebitda = feats["fund_ev_ebitda"]
        quality_score = feats["fund_quality_score"]
        value_score = feats["fund_value_score"]

        # Composite GARP Score [-1.0 .. +1.0]
        # Equal blend of Quality and Value scores [0..1] mapped to [-1..+1]
        garp_score = 0.55 * quality_score + 0.45 * value_score
        score = (garp_score - 0.5) * 2.0  # [-1.0 .. +1.0]
        confidence = 0.5 + abs(score) * 0.5

        # Check quality pass/fail gates
        is_high_quality = (roic >= self.min_roic) and (accrual <= self.max_accrual_ratio)
        is_fair_value = (ev_ebitda <= self.max_ev_ebitda) and (fcf_yield >= self.min_fcf_yield)

        if is_high_quality and is_fair_value:
            score = max(score, 0.4)
            confidence = max(confidence, 0.75)
        elif not is_high_quality and accrual > 0.10:
            # Low quality / aggressive earnings manipulation risk
            score = min(score, -0.4)
            confidence = max(confidence, 0.70)

        rationale = (
            f"L3 GARP Quality & Valuation: ROIC={roic * 100:.1f}%, Sloan Accrual={accrual:.3f}, "
            f"FCF Yield={fcf_yield * 100:.1f}%, EV/EBITDA={ev_ebitda:.1f}x (Quality: {quality_score * 100:.0f}/100, Value: {value_score * 100:.0f}/100)."
        )

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=float(score),
            confidence=float(confidence),
            rationale=rationale,
        )


class EarningsSurpriseSignalProvider(SignalProvider):
    """L3 Alpha Signal Provider: Post-Earnings Announcement Drift (PEAD)."""

    def __init__(
        self,
        id: str = "l3_earnings_surprise",
        version: str = "1.0.0",
        lookback_days: int = 30,
    ) -> None:
        self._id = id
        self._version = version
        self.lookback_days = lookback_days

    @property
    def id(self) -> str:
        return self._id

    @property
    def version(self) -> str:
        return self._version

    @property
    def layer(self) -> SignalLayer:
        return SignalLayer.L3_FUNDAMENTAL

    def warmup_bars(self) -> int:
        return 1

    def evaluate(self, ctx: MarketContext, symbol: Symbol) -> Signal | None:
        snapshot = ctx.fundamentals(symbol)
        if snapshot is None:
            return None

        filing_dt = snapshot.filing_date
        filing_date_obj = filing_dt.date() if hasattr(filing_dt, "date") else filing_dt
        now_date_obj = ctx.now.date() if hasattr(ctx.now, "date") else ctx.now
        age_days = (now_date_obj - filing_date_obj).days
        if age_days < 0 or age_days > self.lookback_days:
            return None

        m = snapshot.metrics
        eps_actual = m.get("eps_actual", m.get("eps", 0.0))
        eps_est = m.get("eps_estimated", 0.0)

        if eps_est == 0.0 or eps_actual == 0.0:
            return None

        surprise_pct = (eps_actual - eps_est) / abs(eps_est)

        # Scale surprise [-50% .. +50%] to [-1.0 .. +1.0]
        score = max(-1.0, min(1.0, surprise_pct * 2.0))
        confidence = 0.5 + min(0.45, abs(surprise_pct))

        rationale = (
            f"L3 PEAD: Standardized EPS surprise {surprise_pct * 100:+.1f}% "
            f"(Actual: ${eps_actual:.2f} vs Est: ${eps_est:.2f})."
        )

        return Signal(
            provider=self.id,
            layer=self.layer,
            symbol=symbol,
            ts=ctx.now,
            score=float(score),
            confidence=float(confidence),
            rationale=rationale,
        )
