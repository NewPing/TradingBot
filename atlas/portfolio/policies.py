"""Position allocation policies converting alpha signals into portfolio target quantities."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from atlas.core.money import Money
from atlas.core.types import BucketId, Position, Quantity, Signal, Symbol
from atlas.portfolio.buckets import DEFAULT_BUCKET_CONFIGS
from atlas.portfolio.sizing import SizingCalculator


class PositionPolicy(Protocol):
    """Protocol for converting market signals and account state into target share quantities."""

    def generate_targets(
        self,
        signals: dict[Symbol, Signal],
        current_positions: list[Position],
        current_prices: dict[Symbol, Decimal],
        total_equity: Money,
        available_cash: Money,
        realized_vols: dict[Symbol, Decimal] | None = None,
    ) -> dict[Symbol, Quantity]:
        """Return desired target share quantity per symbol (0 means exit / flat)."""
        ...


@dataclass(frozen=True, slots=True)
class TopNLongOnlyPolicy:
    """Selects top N symbols ranked by composite score exceeding min_score.

    Non-selected symbols currently held are targeted for exit (qty=0).
    """

    n: int = 5
    min_score: float = 0.2
    weight_by: str = "inverse_vol"  # "inverse_vol", "equal_weight", "conviction"
    max_position_pct: Decimal = Decimal("0.20")
    bucket: BucketId = BucketId.CORE
    scale_by_bucket_allocation: bool = False
    sizing: SizingCalculator = field(default_factory=SizingCalculator)

    def generate_targets(
        self,
        signals: dict[Symbol, Signal],
        current_positions: list[Position],
        current_prices: dict[Symbol, Decimal],
        total_equity: Money,
        available_cash: Money,
        realized_vols: dict[Symbol, Decimal] | None = None,
    ) -> dict[Symbol, Quantity]:
        _ = available_cash
        realized_vols = realized_vols or {}
        targets: dict[Symbol, Quantity] = {}

        # Filter qualifying signals with score >= min_score
        qualifying = [
            (sym, sig)
            for sym, sig in signals.items()
            if sig.score >= self.min_score and current_prices.get(sym, Decimal("0")) > Decimal("0")
        ]

        # Sort descending by score
        qualifying.sort(key=lambda x: (x[1].score, x[1].confidence), reverse=True)
        top_selected = qualifying[: self.n]
        selected_symbols = {sym for sym, _ in top_selected}

        # Any currently held position in this bucket not in selected set -> target 0 (liquidate)
        for pos in current_positions:
            if pos.bucket == self.bucket and pos.symbol not in selected_symbols:
                targets[pos.symbol] = Quantity(0)

        if not top_selected:
            return targets

        bucket_cfg = DEFAULT_BUCKET_CONFIGS.get(self.bucket)
        bucket_alloc = (
            bucket_cfg.target_allocation
            if (self.scale_by_bucket_allocation and bucket_cfg)
            else Decimal("1.0")
        )
        effective_bucket_equity = Money(total_equity.amount * bucket_alloc, total_equity.currency)

        if self.weight_by == "equal_weight":
            equal_weight = min(Decimal("1.0") / Decimal(len(top_selected)), self.max_position_pct)
            for sym, _ in top_selected:
                px = current_prices[sym]
                notional = effective_bucket_equity.amount * equal_weight
                qty = int(math.floor(float(notional / px)))
                targets[sym] = Quantity(max(0, qty))
        elif self.weight_by == "conviction":
            total_conviction = (
                sum(max(0.1, sig.score * sig.confidence) for _, sig in top_selected) or 1.0
            )
            for sym, sig in top_selected:
                px = current_prices[sym]
                conv_score = max(0.1, sig.score * sig.confidence)
                conv_weight = min(
                    Decimal(str(conv_score / total_conviction)),
                    self.max_position_pct,
                )
                notional = effective_bucket_equity.amount * conv_weight
                qty = int(math.floor(float(notional / px)))
                targets[sym] = Quantity(max(0, qty))
        else:
            # Volatility targeting via SizingCalculator (inverse_vol)
            for sym, sig in top_selected:
                px = current_prices[sym]
                vol = realized_vols.get(sym, Decimal("0.20"))
                qty = self.sizing.calculate_quantity(
                    bucket=self.bucket,
                    bucket_equity=effective_bucket_equity,
                    price=px,
                    composite_score=sig.score,
                    realized_vol_20d=vol,
                    expected_n_positions=self.n,
                    max_position_pct=self.max_position_pct,
                )
                targets[sym] = qty

        return targets


@dataclass(frozen=True, slots=True)
class ThresholdLongOnlyPolicy:
    """Hysteresis threshold policy with optional shorting support for SWING bucket.

    Enters long on score >= enter_threshold, exits long on score <= exit_threshold.
    If allow_short is True: enters short on score <= -enter_threshold, exits short on score >= -exit_threshold.
    """

    enter_threshold: float = 0.3
    exit_threshold: float = -0.1
    max_positions: int = 10
    bucket: BucketId = BucketId.SWING
    max_position_pct: Decimal = Decimal("0.10")
    allow_short: bool = False
    scale_by_bucket_allocation: bool = False
    sizing: SizingCalculator = field(default_factory=SizingCalculator)

    def generate_targets(
        self,
        signals: dict[Symbol, Signal],
        current_positions: list[Position],
        current_prices: dict[Symbol, Decimal],
        total_equity: Money,
        available_cash: Money,
        realized_vols: dict[Symbol, Decimal] | None = None,
    ) -> dict[Symbol, Quantity]:
        _ = available_cash
        realized_vols = realized_vols or {}
        targets: dict[Symbol, Quantity] = {}
        currently_held = {pos.symbol: pos for pos in current_positions if pos.qty != 0}

        # Check exits first
        for sym, pos in currently_held.items():
            sig = signals.get(sym)
            if pos.qty > 0:
                # Long position exit (hold if signal missing)
                if sig is not None and sig.score <= self.exit_threshold:
                    targets[sym] = Quantity(0)
                else:
                    targets[sym] = Quantity(pos.qty)
            else:
                # Short position exit (hold if signal missing)
                if sig is not None and sig.score >= -self.exit_threshold:
                    targets[sym] = Quantity(0)
                else:
                    targets[sym] = Quantity(pos.qty)

        active_count = len([s for s, q in targets.items() if q != 0])

        # Check new entries
        long_candidates = [
            (sym, sig)
            for sym, sig in signals.items()
            if sym not in currently_held
            and sig.score >= self.enter_threshold
            and current_prices.get(sym, Decimal("0")) > Decimal("0")
        ]
        long_candidates.sort(key=lambda x: x[1].score, reverse=True)

        bucket_cfg = DEFAULT_BUCKET_CONFIGS.get(self.bucket)
        bucket_alloc = (
            bucket_cfg.target_allocation
            if (self.scale_by_bucket_allocation and bucket_cfg)
            else Decimal("1.0")
        )
        effective_bucket_equity = Money(total_equity.amount * bucket_alloc, total_equity.currency)

        for sym, sig in long_candidates:
            if active_count >= self.max_positions:
                break
            px = current_prices[sym]
            vol = realized_vols.get(sym, Decimal("0.20"))
            qty = self.sizing.calculate_quantity(
                bucket=self.bucket,
                bucket_equity=effective_bucket_equity,
                price=px,
                composite_score=sig.score,
                realized_vol_20d=vol,
                expected_n_positions=self.max_positions,
                max_position_pct=self.max_position_pct,
            )
            if qty > 0:
                targets[sym] = qty
                active_count += 1

        # Check short entries if enabled and in SWING bucket
        if self.allow_short and self.bucket == BucketId.SWING:
            short_candidates = [
                (sym, sig)
                for sym, sig in signals.items()
                if sym not in currently_held
                and sig.score <= -self.enter_threshold
                and current_prices.get(sym, Decimal("0")) > Decimal("0")
            ]
            short_candidates.sort(key=lambda x: x[1].score)  # most negative first

            for sym, sig in short_candidates:
                if active_count >= self.max_positions:
                    break
                px = current_prices[sym]
                vol = realized_vols.get(sym, Decimal("0.20"))
                qty = self.sizing.calculate_quantity(
                    bucket=self.bucket,
                    bucket_equity=effective_bucket_equity,
                    price=px,
                    composite_score=abs(sig.score),
                    realized_vol_20d=vol,
                    expected_n_positions=self.max_positions,
                    max_position_pct=self.max_position_pct,
                )
                if qty > 0:
                    targets[sym] = Quantity(-qty)
                    active_count += 1

        return targets


# Alias for explicitly named long/short policy
ThresholdLongShortPolicy = ThresholdLongOnlyPolicy


@dataclass(frozen=True, slots=True)
class TargetWeightPolicy:
    """Direct proportional mapping from composite score to target portfolio weight."""

    bucket: BucketId = BucketId.CORE
    max_position_pct: Decimal = Decimal("0.20")
    min_score: float = 0.05

    def generate_targets(
        self,
        signals: dict[Symbol, Signal],
        current_positions: list[Position],
        current_prices: dict[Symbol, Decimal],
        total_equity: Money,
        available_cash: Money,
        realized_vols: dict[Symbol, Decimal] | None = None,
    ) -> dict[Symbol, Quantity]:
        _ = (available_cash, realized_vols)
        targets: dict[Symbol, Quantity] = {}

        for pos in current_positions:
            if pos.bucket == self.bucket and (
                pos.symbol not in signals or signals[pos.symbol].score < self.min_score
            ):
                targets[pos.symbol] = Quantity(0)

        for sym, sig in signals.items():
            if sig.score < self.min_score:
                continue
            px = current_prices.get(sym, Decimal("0"))
            if px <= Decimal("0"):
                continue

            target_pct = min(Decimal(str(sig.score)) * self.max_position_pct, self.max_position_pct)
            target_notional = total_equity.amount * target_pct
            qty = int(math.floor(float(target_notional / px)))
            targets[sym] = Quantity(max(0, qty))

        return targets
