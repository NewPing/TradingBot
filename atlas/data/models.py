"""SQLAlchemy models for ATLAS market data, instruments, corporate actions, and data health."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ATLAS SQLAlchemy models."""

    pass


class Instrument(Base):
    """Tradable equity or ETF instrument."""

    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="US")
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    listed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    delisted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_etf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    adv_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)


class UniverseSnapshot(Base):
    """Point-in-time universe / index membership record to avoid survivorship bias."""

    __tablename__ = "universe_snapshots"
    __table_args__ = (
        PrimaryKeyConstraint("snapshot_date", "symbol"),
        Index("ix_universe_snapshots_date", "snapshot_date"),
    )

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)


class Bar1D(Base):
    """Daily OHLCV bar with split/dividend adjustment factors."""

    __tablename__ = "bars_1d"
    __table_args__ = (
        PrimaryKeyConstraint("symbol", "ts"),
        Index("ix_bars_1d_symbol_ts", "symbol", "ts"),
        Index("ix_bars_1d_ts", "ts"),
    )

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    adj_factor: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, default=Decimal("1.0")
    )
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="tiingo")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class CorporateAction(Base):
    """Stock splits, dividends, or mergers affecting price series."""

    __tablename__ = "corporate_actions"
    __table_args__ = (Index("ix_corporate_actions_symbol_ex_date", "symbol", "ex_date"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SPLIT, DIVIDEND, MERGER
    ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 8), nullable=True
    )  # Split ratio (e.g., 2.0 for 2-for-1)
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )  # Dividend amount per share


class DataHealth(Base):
    """Audit log of data validation checks, missing bars, and anomalies."""

    __tablename__ = "data_health"
    __table_args__ = (
        Index("ix_data_health_check_ts", "check_name", "ts"),
        Index("ix_data_health_symbol", "symbol"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # INFO, WARNING, CRITICAL
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
