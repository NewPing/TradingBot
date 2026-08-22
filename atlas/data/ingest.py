"""Data ingestion pipeline coordinating fetching, normalizing, validating, and persisting."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.core.types import Bar, Symbol
from atlas.data.models import Bar1D, CorporateAction, DataHealth, Instrument
from atlas.data.normalize import (
    compute_adjusted_series,
    normalize_alpaca_bar,
    normalize_tiingo_bar,
    normalize_yfinance_bar,
)
from atlas.data.providers.base import BaseDataProvider
from atlas.data.providers.tiingo import TiingoProvider
from atlas.data.validate import DataValidator, ValidationIssue

logger = logging.getLogger("atlas.data.ingest")


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Summary of an ingestion run for a single symbol."""

    symbol: Symbol
    start_date: date
    end_date: date
    bars_ingested: int
    corporate_actions_count: int
    issues_found: int


class DataIngestPipeline:
    """Orchestrates provider data fetching, normalization, §4.5 validation, and DB persistence."""

    def __init__(
        self,
        primary_provider: BaseDataProvider | None = None,
        secondary_provider: BaseDataProvider | None = None,
    ) -> None:
        self.primary_provider = primary_provider or TiingoProvider()
        self.secondary_provider = secondary_provider

    async def ingest_symbol(
        self,
        symbol: Symbol,
        start_date: date,
        end_date: date,
        session: Session | None = None,
    ) -> tuple[list[Bar], list[ValidationIssue], IngestionResult]:
        """
        Fetch, normalize, validate, and optionally persist data for a symbol across a date range.
        """
        logger.info("Ingesting symbol %s from %s to %s", symbol, start_date, end_date)

        # 1. Fetch raw data from primary provider
        raw_bars = await self.primary_provider.fetch_daily_bars(symbol, start_date, end_date)
        raw_actions = await self.primary_provider.fetch_corporate_actions(
            symbol, start_date, end_date
        )

        # 2. Normalize raw bars
        normalized_bars: list[Bar] = []
        for raw in raw_bars:
            if self.primary_provider.name == "tiingo":
                normalized_bars.append(normalize_tiingo_bar(raw, symbol))
            elif self.primary_provider.name == "alpaca":
                normalized_bars.append(normalize_alpaca_bar(raw, symbol))
            elif self.primary_provider.name == "yfinance":
                normalized_bars.append(normalize_yfinance_bar(raw, symbol))
            else:
                # Default to Tiingo format
                normalized_bars.append(normalize_tiingo_bar(raw, symbol))

        # 3. Apply corporate actions adjustment
        adjusted_bars = compute_adjusted_series(normalized_bars, raw_actions)

        # 4. Optional secondary provider fetch for cross-source validation
        secondary_bars: list[Bar] | None = None
        if self.secondary_provider:
            try:
                sec_raw = await self.secondary_provider.fetch_daily_bars(
                    symbol, start_date, end_date
                )
                secondary_bars = [
                    normalize_alpaca_bar(r, symbol)
                    if self.secondary_provider.name == "alpaca"
                    else normalize_yfinance_bar(r, symbol)
                    for r in sec_raw
                ]
            except Exception as e:
                logger.warning("Secondary provider fetch failed for %s: %s", symbol, e)

        # 5. Run §4.5 validation
        issues = DataValidator.validate_full_series(
            symbol=symbol,
            bars=adjusted_bars,
            start_date=start_date,
            end_date=end_date,
            corporate_actions=raw_actions,
            secondary_bars=secondary_bars,
        )

        # 6. Database persistence (if session provided)
        if session:
            self._persist_to_db(session, symbol, adjusted_bars, raw_actions, issues)

        result = IngestionResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            bars_ingested=len(adjusted_bars),
            corporate_actions_count=len(raw_actions),
            issues_found=len(issues),
        )

        return adjusted_bars, issues, result

    def _persist_to_db(
        self,
        session: Session,
        symbol: Symbol,
        bars: Sequence[Bar],
        actions: Sequence[dict[str, Any]],
        issues: Sequence[ValidationIssue],
    ) -> None:
        """Persist bars, corporate actions, and health check audit records to DB."""
        # Upsert instrument record if not exists
        stmt = select(Instrument).where(Instrument.symbol == str(symbol))
        inst = session.scalars(stmt).first()
        if not inst:
            session.add(
                Instrument(
                    symbol=str(symbol),
                    name=str(symbol),
                    exchange="US",
                )
            )

        # Persist bars
        for b in bars:
            existing_bar = session.get(Bar1D, (str(b.symbol), b.ts))
            if existing_bar:
                existing_bar.open = b.open
                existing_bar.high = b.high
                existing_bar.low = b.low
                existing_bar.close = b.close
                existing_bar.volume = b.volume
                existing_bar.adj_factor = b.adj_factor
                existing_bar.vwap = b.vwap
                existing_bar.source = b.source
            else:
                session.add(
                    Bar1D(
                        symbol=str(b.symbol),
                        ts=b.ts,
                        open=b.open,
                        high=b.high,
                        low=b.low,
                        close=b.close,
                        volume=b.volume,
                        adj_factor=b.adj_factor,
                        vwap=b.vwap,
                        source=b.source,
                    )
                )

        # Persist corporate actions
        for act in actions:
            ex_d = act["ex_date"]
            if isinstance(ex_d, str):
                ex_d = date.fromisoformat(ex_d.split("T")[0])
            session.add(
                CorporateAction(
                    symbol=str(symbol),
                    ex_date=ex_d,
                    action_type=str(act.get("action_type", "")).upper(),
                    ratio=Decimal(str(act["ratio"])) if act.get("ratio") is not None else None,
                    amount=Decimal(str(act["amount"])) if act.get("amount") is not None else None,
                )
            )

        # Persist validation issues
        for issue in issues:
            session.add(
                DataHealth(
                    check_name=issue.check_name,
                    ts=issue.ts,
                    symbol=str(issue.symbol) if issue.symbol else None,
                    severity=str(issue.severity),
                    detail=issue.detail,
                )
            )

        session.commit()
