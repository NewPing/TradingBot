"""Data normalization and corporate action adjustments for market data."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from atlas.core.types import Bar, Symbol

# Standard NYSE daily bar close time in UTC (21:00:00 UTC is 16:00:00 ET / 17:00:00 EDT)
NYSE_CLOSE_TIME_UTC = time(21, 0, 0, tzinfo=UTC)
FOUR_PLACES = Decimal("0.0001")
EIGHT_PLACES = Decimal("0.00000001")


def _to_decimal(val: Any, precision: Decimal = FOUR_PLACES) -> Decimal:
    if isinstance(val, Decimal):
        return val.quantize(precision, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(precision, rounding=ROUND_HALF_UP)


def parse_date_to_utc_close(date_val: Any) -> datetime:
    """Parse date or date string into UTC datetime at 21:00:00 UTC (NYSE close)."""
    if isinstance(date_val, datetime):
        if date_val.tzinfo is None:
            return date_val.replace(tzinfo=UTC)
        return date_val.astimezone(UTC)
    elif isinstance(date_val, date):
        return datetime.combine(date_val, time(21, 0, 0, tzinfo=UTC))
    elif isinstance(date_val, str):
        # Handle ISO strings like "2023-01-03T00:00:00.000Z" or "2023-01-03"
        clean_date_str = date_val.split("T")[0]
        parsed_d = date.fromisoformat(clean_date_str)
        return datetime.combine(parsed_d, time(21, 0, 0, tzinfo=UTC))
    raise ValueError(f"Cannot parse date from {type(date_val)}: {date_val}")


def normalize_tiingo_bar(raw: dict[str, Any], symbol: Symbol) -> Bar:
    """Convert Tiingo raw daily price dictionary to a frozen Bar object."""
    ts = parse_date_to_utc_close(raw["date"])
    open_px = _to_decimal(raw["open"])
    high_px = _to_decimal(raw["high"])
    low_px = _to_decimal(raw["low"])
    close_px = _to_decimal(raw["close"])
    volume = int(raw.get("volume", 0) or 0)

    # Sanity checks and bounds normalization
    high_px = max(high_px, open_px, close_px)
    low_px = min(low_px, open_px, close_px)

    adj_close = _to_decimal(raw.get("adjClose", close_px))
    adj_factor = Decimal("1.0")
    if close_px > 0:
        adj_factor = (adj_close / close_px).quantize(EIGHT_PLACES, rounding=ROUND_HALF_UP)

    return Bar(
        symbol=symbol,
        ts=ts,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        volume=max(0, volume),
        adj_factor=adj_factor,
        source="tiingo",
        resolution="1d",
    )


def normalize_alpaca_bar(raw: dict[str, Any], symbol: Symbol) -> Bar:
    """Convert Alpaca market data v2 daily bar dictionary to a frozen Bar object."""
    ts = parse_date_to_utc_close(raw["t"])
    open_px = _to_decimal(raw["o"])
    high_px = _to_decimal(raw["h"])
    low_px = _to_decimal(raw["l"])
    close_px = _to_decimal(raw["c"])
    volume = int(raw.get("v", 0) or 0)
    vwap_raw = raw.get("vw")
    vwap_px = _to_decimal(vwap_raw) if vwap_raw is not None else None

    high_px = max(high_px, open_px, close_px)
    low_px = min(low_px, open_px, close_px)

    return Bar(
        symbol=symbol,
        ts=ts,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        volume=max(0, volume),
        adj_factor=Decimal("1.0"),
        vwap=vwap_px,
        source="alpaca",
        resolution="1d",
    )


def normalize_yfinance_bar(raw: dict[str, Any], symbol: Symbol) -> Bar:
    """Convert yfinance bar dictionary to a frozen Bar object."""
    ts = parse_date_to_utc_close(raw["date"])
    open_px = _to_decimal(raw["open"])
    high_px = _to_decimal(raw["high"])
    low_px = _to_decimal(raw["low"])
    close_px = _to_decimal(raw["close"])
    volume = int(raw.get("volume", 0) or 0)

    high_px = max(high_px, open_px, close_px)
    low_px = min(low_px, open_px, close_px)

    adj_close = _to_decimal(raw.get("adj_close", close_px))
    adj_factor = Decimal("1.0")
    if close_px > 0:
        adj_factor = (adj_close / close_px).quantize(EIGHT_PLACES, rounding=ROUND_HALF_UP)

    return Bar(
        symbol=symbol,
        ts=ts,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        volume=max(0, volume),
        adj_factor=adj_factor,
        source="yfinance",
        resolution="1d",
    )


def compute_adjusted_series(
    bars: Sequence[Bar],
    corporate_actions: Sequence[dict[str, Any]],
) -> list[Bar]:
    """
    Calculate backward adjustment factors for a sequence of Bars given corporate actions.
    Applies splits and cash dividends recursively backwards from the most recent bar.
    """
    if not bars:
        return []

    # Sort bars chronologically
    sorted_bars = sorted(bars, key=lambda b: b.ts)

    # Map ex_date -> list of actions
    actions_by_date: dict[date, list[dict[str, Any]]] = {}
    for ca in corporate_actions:
        ex_d = ca["ex_date"]
        if isinstance(ex_d, str):
            ex_d = date.fromisoformat(ex_d.split("T")[0])
        elif isinstance(ex_d, datetime):
            ex_d = ex_d.date()
        actions_by_date.setdefault(ex_d, []).append(ca)

    n = len(sorted_bars)
    adj_factors: list[Decimal] = [Decimal("1.0")] * n
    cumulative_factor = Decimal("1.0")

    # Walk backwards from newest to oldest bar
    for i in range(n - 1, -1, -1):
        bar = sorted_bars[i]
        bar_d = bar.ts.date()

        # The current bar receives the current cumulative factor
        adj_factors[i] = cumulative_factor

        # If there are corporate actions on this ex_date, adjust historical prices preceding it (< i)
        if bar_d in actions_by_date:
            for act in actions_by_date[bar_d]:
                act_type = act.get("action_type", "").upper()
                if act_type == "SPLIT":
                    split_ratio = _to_decimal(act.get("ratio", 1.0), precision=EIGHT_PLACES)
                    if split_ratio > 0:
                        cumulative_factor = (cumulative_factor / split_ratio).quantize(
                            EIGHT_PLACES, rounding=ROUND_HALF_UP
                        )
                elif act_type == "DIVIDEND":
                    div_amount = _to_decimal(act.get("amount", 0.0), precision=FOUR_PLACES)
                    prev_close = sorted_bars[i - 1].close if i > 0 else bar.close
                    if prev_close > 0 and div_amount > 0:
                        div_factor = max(
                            Decimal("0.00000001"),
                            ((prev_close - div_amount) / prev_close).quantize(
                                EIGHT_PLACES, rounding=ROUND_HALF_UP
                            ),
                        )
                        cumulative_factor = (cumulative_factor * div_factor).quantize(
                            EIGHT_PLACES, rounding=ROUND_HALF_UP
                        )

    adjusted_bars: list[Bar] = []
    for bar, factor in zip(sorted_bars, adj_factors, strict=True):
        adjusted_bars.append(
            Bar(
                symbol=bar.symbol,
                ts=bar.ts,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                adj_factor=factor,
                vwap=bar.vwap,
                source=bar.source,
                resolution=bar.resolution,
            )
        )

    return adjusted_bars
