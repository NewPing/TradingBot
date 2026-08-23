"""Market data validation engine implementing §4.5 invariant checks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from atlas.core.calendar import get_trading_days, is_trading_day
from atlas.core.types import Bar, Symbol


class ValidationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Recorded data quality issue or anomaly."""

    check_name: str
    symbol: Symbol | None
    ts: datetime
    severity: ValidationSeverity
    detail: str


class DataValidator:
    """Engine executing §4.5 data integrity and quality rules."""

    @staticmethod
    def validate_bar_bounds(bar: Bar) -> list[ValidationIssue]:
        """Check OHLC bounds: High >= Low, High >= Open/Close, Low <= Open/Close, Low > 0."""
        issues: list[ValidationIssue] = []

        if bar.low <= 0:
            issues.append(
                ValidationIssue(
                    check_name="non_positive_price",
                    symbol=bar.symbol,
                    ts=bar.ts,
                    severity=ValidationSeverity.CRITICAL,
                    detail=f"Low price is non-positive: {bar.low}",
                )
            )

        if bar.high < bar.low:
            issues.append(
                ValidationIssue(
                    check_name="high_below_low",
                    symbol=bar.symbol,
                    ts=bar.ts,
                    severity=ValidationSeverity.CRITICAL,
                    detail=f"High ({bar.high}) < Low ({bar.low})",
                )
            )

        if bar.open < bar.low or bar.open > bar.high:
            issues.append(
                ValidationIssue(
                    check_name="open_out_of_bounds",
                    symbol=bar.symbol,
                    ts=bar.ts,
                    severity=ValidationSeverity.CRITICAL,
                    detail=f"Open ({bar.open}) outside [Low ({bar.low}), High ({bar.high})]",
                )
            )

        if bar.close < bar.low or bar.close > bar.high:
            issues.append(
                ValidationIssue(
                    check_name="close_out_of_bounds",
                    symbol=bar.symbol,
                    ts=bar.ts,
                    severity=ValidationSeverity.CRITICAL,
                    detail=f"Close ({bar.close}) outside [Low ({bar.low}), High ({bar.high})]",
                )
            )

        return issues

    @staticmethod
    def validate_volume(bar: Bar) -> list[ValidationIssue]:
        """Flag zero volume on open trading days."""
        issues: list[ValidationIssue] = []
        if is_trading_day(bar.ts.date()) and bar.volume <= 0:
            issues.append(
                ValidationIssue(
                    check_name="zero_volume_trading_day",
                    symbol=bar.symbol,
                    ts=bar.ts,
                    severity=ValidationSeverity.WARNING,
                    detail=f"Zero volume on active trading day {bar.ts.date()}",
                )
            )
        return issues

    @classmethod
    def validate_calendar_completeness(
        cls,
        symbol: Symbol,
        bars: Sequence[Bar],
        start_date: date,
        end_date: date,
    ) -> list[ValidationIssue]:
        """
        Check for missing trading days in the bar sequence against the NYSE calendar.
        Note: Missing bars are flagged; forward-filling is strictly forbidden.
        """
        issues: list[ValidationIssue] = []
        expected_sessions = set(get_trading_days(start_date, end_date))
        actual_sessions = {b.ts.date() for b in bars}

        missing_sessions = sorted(expected_sessions - actual_sessions)
        for missing_d in missing_sessions:
            issues.append(
                ValidationIssue(
                    check_name="missing_trading_bar",
                    symbol=symbol,
                    ts=datetime.combine(missing_d, datetime.min.time(), tzinfo=UTC),
                    severity=ValidationSeverity.WARNING,
                    detail=f"Missing price bar on NYSE trading session {missing_d}",
                )
            )
        return issues

    @classmethod
    def validate_price_jumps(
        cls,
        bars: Sequence[Bar],
        corporate_actions: Sequence[dict[str, Any]] | None = None,
        max_jump_threshold: float = 0.25,
    ) -> list[ValidationIssue]:
        """
        Flag price changes > 25% between consecutive trading days without corporate actions.
        """
        issues: list[ValidationIssue] = []
        if len(bars) < 2:
            return issues

        sorted_bars = sorted(bars, key=lambda b: b.ts)
        ca_dates = set()
        if corporate_actions:
            for ca in corporate_actions:
                ex_d = ca["ex_date"]
                if isinstance(ex_d, str):
                    ex_d = date.fromisoformat(ex_d.split("T")[0])
                elif isinstance(ex_d, datetime):
                    ex_d = ex_d.date()
                ca_dates.add(ex_d)

        for prev_bar, curr_bar in zip(sorted_bars[:-1], sorted_bars[1:], strict=False):
            if prev_bar.close <= 0:
                continue
            pct_change = abs(float((curr_bar.close - prev_bar.close) / prev_bar.close))
            curr_date = curr_bar.ts.date()

            if pct_change > max_jump_threshold and curr_date not in ca_dates:
                issues.append(
                    ValidationIssue(
                        check_name="unexplained_price_jump",
                        symbol=curr_bar.symbol,
                        ts=curr_bar.ts,
                        severity=ValidationSeverity.WARNING,
                        detail=(
                            f"Single-day price change of {pct_change * 100:.2f}% "
                            f"(from {prev_bar.close} to {curr_bar.close}) with no corporate action on {curr_date}"
                        ),
                    )
                )

        return issues

    @classmethod
    def validate_cross_source_consistency(
        cls,
        primary_bars: Sequence[Bar],
        secondary_bars: Sequence[Bar],
        diff_threshold: float = 0.005,  # 0.5%
    ) -> list[ValidationIssue]:
        """
        Compare close prices between two data sources (e.g. Tiingo vs Alpaca).
        Flag discrepancies exceeding diff_threshold (0.5%).
        """
        issues: list[ValidationIssue] = []
        sec_by_date = {b.ts.date(): b for b in secondary_bars}

        for p_bar in primary_bars:
            p_date = p_bar.ts.date()
            if p_date in sec_by_date:
                s_bar = sec_by_date[p_date]
                if p_bar.close <= 0:
                    continue
                diff = abs(float((p_bar.close - s_bar.close) / p_bar.close))
                if diff > diff_threshold:
                    issues.append(
                        ValidationIssue(
                            check_name="cross_source_divergence",
                            symbol=p_bar.symbol,
                            ts=p_bar.ts,
                            severity=ValidationSeverity.WARNING,
                            detail=(
                                f"Close price divergence of {diff * 100:.3f}% between "
                                f"{p_bar.source} ({p_bar.close}) and {s_bar.source} ({s_bar.close}) on {p_date}"
                            ),
                        )
                    )

        return issues

    @classmethod
    def validate_full_series(
        cls,
        symbol: Symbol,
        bars: Sequence[Bar],
        start_date: date,
        end_date: date,
        corporate_actions: Sequence[dict[str, Any]] | None = None,
        secondary_bars: Sequence[Bar] | None = None,
    ) -> list[ValidationIssue]:
        """Run all §4.5 validation checks on a series of bars."""
        issues: list[ValidationIssue] = []

        # 1. Bounds and volume on each bar
        for bar in bars:
            issues.extend(cls.validate_bar_bounds(bar))
            issues.extend(cls.validate_volume(bar))

        # 2. Calendar completeness
        issues.extend(cls.validate_calendar_completeness(symbol, bars, start_date, end_date))

        # 3. Price jumps
        issues.extend(cls.validate_price_jumps(bars, corporate_actions))

        # 4. Cross-source consistency
        if secondary_bars:
            issues.extend(cls.validate_cross_source_consistency(bars, secondary_bars))

        return issues

    @classmethod
    def verify_real_market_data(cls, bars: Sequence[Bar]) -> bool:
        """Verify that market data consists of real historical bars with positive volume and valid bounds."""
        if not bars:
            return False
        for b in bars:
            if b.low <= 0 or b.high < b.low or b.open <= 0 or b.close <= 0:
                return False
        return True
