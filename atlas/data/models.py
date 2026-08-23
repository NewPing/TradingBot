"""SQLAlchemy models for ATLAS market data, instruments, corporate actions, and data health."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class StrategyVersion(Base):
    """Versioned trading strategy specification with immutable lineage."""

    __tablename__ = "strategy_versions"
    __table_args__ = (
        Index("ix_strategy_versions_family", "family"),
        Index("ix_strategy_versions_spec_hash", "spec_hash"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    spec_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("strategy_versions.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RESEARCH")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    parent: Mapped[StrategyVersion | None] = relationship(
        "StrategyVersion", remote_side=[id], backref="children"
    )
    runs: Mapped[list[Run]] = relationship("Run", back_populates="strategy_version")


class Run(Base):
    """Backtest, paper, shadow, or live execution run with full reproducibility metadata."""

    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_strategy_version_id", "strategy_version_id"),
        Index("ix_runs_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("strategy_versions.id"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="BACKTEST")
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    universe_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=42)
    git_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cost_model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    lib_versions: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    summary_metrics: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    strategy_version: Mapped[StrategyVersion] = relationship(
        "StrategyVersion", back_populates="runs"
    )
    metrics: Mapped[list[RunMetric]] = relationship("RunMetric", back_populates="run")
    equity_curve: Mapped[list[EquityPoint]] = relationship("EquityPoint", back_populates="run")
    trades: Mapped[list[RunTrade]] = relationship("RunTrade", back_populates="run")


class RunMetric(Base):
    """Key-value performance metric for a specific run."""

    __tablename__ = "run_metrics"
    __table_args__ = (Index("ix_run_metrics_run_metric", "run_id", "metric_name"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    window: Mapped[str] = mapped_column(String(32), nullable=False, default="FULL")

    run: Mapped[Run] = relationship("Run", back_populates="metrics")


class EquityPoint(Base):
    """Point-in-time portfolio equity observation for backtest/live runs."""

    __tablename__ = "equity_curve"
    __table_args__ = (Index("ix_equity_curve_run_ts", "run_id", "ts"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    per_bucket: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=Decimal("0"))

    run: Mapped[Run] = relationship("Run", back_populates="equity_curve")


class RunTrade(Base):
    """Completed trade execution record associated with a run."""

    __tablename__ = "run_trades"
    __table_args__ = (
        Index("ix_run_trades_run_id", "run_id"),
        Index("ix_run_trades_symbol", "symbol"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    trade_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # LONG | SHORT
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pnl_net: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    return_pct: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    slippage: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    exit_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="SIGNAL")

    run: Mapped[Run] = relationship("Run", back_populates="trades")


class Trial(Base):
    """Sacred multiple-testing trial record for overfitting and deflated Sharpe accounting."""

    __tablename__ = "trials"
    __table_args__ = (
        Index("ix_trials_family", "family"),
        Index("ix_trials_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    hypothesis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("runs.id"), nullable=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metrics: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class OrderRecord(Base):
    """Trading order persisted in system of record."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_run_id", "run_id"),
        Index("ix_orders_symbol", "symbol"),
        Index("ix_orders_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    strategy_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("strategy_versions.id"), nullable=False
    )
    bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)  # BUY | SELL
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_type: Mapped[str] = mapped_column(String(32), nullable=False)
    tif: Mapped[str] = mapped_column(String(16), nullable=False, default="DAY")
    limit_px: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    stop_px: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    broker_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class FillRecord(Base):
    """Broker execution fill event record."""

    __tablename__ = "fills"
    __table_args__ = (
        Index("ix_fills_order_id", "order_id"),
        Index("ix_fills_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("orders.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0"))
    slippage_est: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    venue: Mapped[str] = mapped_column(String(32), nullable=False, default="ALPACA_PAPER")


class PositionSnapshot(Base):
    """Point-in-time snapshot of open positions."""

    __tablename__ = "positions_snapshots"
    __table_args__ = (Index("ix_positions_snapshots_run_id_ts", "run_id", "ts"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[int] = mapped_column(BigInteger, nullable=False)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class KillSwitchEventRecord(Base):
    """Audit log of all triggered and resolved kill switch incidents."""

    __tablename__ = "kill_switch_events"
    __table_args__ = (
        Index("ix_kill_switch_events_ts", "ts"),
        Index("ix_kill_switch_events_trigger", "trigger"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FundamentalFiling(Base):
    """Point-in-time fundamental filing record with SEC EDGAR filing timestamps."""

    __tablename__ = "fundamentals_pit"
    __table_args__ = (
        Index("ix_fundamentals_pit_symbol_filing", "symbol", "filing_date"),
        Index("ix_fundamentals_pit_filing_date", "filing_date"),
        Index("ix_fundamentals_pit_symbol_report", "symbol", "report_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # Q1, Q2, Q3, Q4, FY
    statement_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INCOME_BALANCE_CASH"
    )
    metrics: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class EarningsEvent(Base):
    """Scheduled and historical earnings announcement release record."""

    __tablename__ = "earnings_events"
    __table_args__ = (
        Index("ix_earnings_events_symbol_date", "symbol", "event_date"),
        Index("ix_earnings_events_event_date", "event_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_of_day: Mapped[str] = mapped_column(
        String(16), nullable=False, default="AMC"
    )  # BMO | AMC | DURING
    fiscal_period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    eps_estimated: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    eps_actual: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    revenue_estimated: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    revenue_actual: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class NewsArticle(Base):
    """Point-in-time financial news article ingested from providers."""

    __tablename__ = "news_articles"
    __table_args__ = (
        Index("ix_news_articles_published_at", "published_at"),
        Index("ix_news_articles_content_hash", "content_hash"),
        Index("ix_news_articles_source", "source"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="alpaca_news")
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbols: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON list of symbols
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    scores: Mapped[list[NewsScore]] = relationship(
        "NewsScore", back_populates="article", cascade="all, delete-orphan"
    )


class NewsScore(Base):
    """Structured LLM sentiment and narrative score for a news article."""

    __tablename__ = "news_scores"
    __table_args__ = (
        Index("ix_news_scores_article_id", "article_id"),
        Index("ix_news_scores_prompt_version", "prompt_version"),
        Index("ix_news_scores_scored_at", "scored_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    article_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("news_articles.id"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    relevance_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    horizon: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SHORT_TERM"
    )  # INTRADAY | SHORT_TERM | MEDIUM_TERM | LONG_TERM
    novelty_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0.5")
    )
    impact: Mapped[str] = mapped_column(
        String(16), nullable=False, default="NEUTRAL"
    )  # BULLISH | BEARISH | NEUTRAL
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, default=Decimal("0.8")
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    article: Mapped[NewsArticle] = relationship("NewsArticle", back_populates="scores")


class PromptTemplate(Base):
    """Versioned prompt template artifact for reproducible LLM inferences."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("ix_prompt_templates_name_version", "name", "version", unique=True),
        Index("ix_prompt_templates_hash", "prompt_hash"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ResearchHypothesis(Base):
    """Generated research hypothesis or candidate strategy variant (Phase 8)."""

    __tablename__ = "research_hypotheses"
    __table_args__ = (
        Index("ix_research_hypotheses_family", "family"),
        Index("ix_research_hypotheses_status", "status"),
        Index("ix_research_hypotheses_generator", "generator_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # PARAM_REFINEMENT | FEATURE_COMBO | REGIME_VARIANT | GENETIC_RECOMBINATION | MANUAL
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_spec_name: Mapped[str] = mapped_column(String(128), nullable=False)
    proposed_spec: Mapped[str] = mapped_column(Text, nullable=False)  # YAML or JSON
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prior_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0.0")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="QUEUED"
    )  # QUEUED | SWEEPING | GATED | VALIDATED | REJECTED | PROMOTED
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ResearchSweep(Base):
    """Parameter or feature exploration sweep batch record (Phase 8)."""

    __tablename__ = "research_sweeps"
    __table_args__ = (
        Index("ix_research_sweeps_hypothesis_id", "hypothesis_id"),
        Index("ix_research_sweeps_family", "family"),
        Index("ix_research_sweeps_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("research_hypotheses.id"), nullable=True
    )
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    sweep_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="GRID"
    )  # GRID | RANDOM | BAYESIAN | PERTURBATION
    param_grid: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    total_combinations: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_combinations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_candidate_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_metric_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="sharpe_ratio"
    )
    best_metric_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING | RUNNING | COMPLETED | FAILED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchReport(Base):
    """Comprehensive statistical research report and candidate evaluation record (Phase 8)."""

    __tablename__ = "research_reports"
    __table_args__ = (
        Index("ix_research_reports_hypothesis_id", "hypothesis_id"),
        Index("ix_research_reports_family", "family"),
        Index("ix_research_reports_verdict", "verdict"),
        Index("ix_research_reports_human_decision", "human_decision"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hypothesis_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("research_hypotheses.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_spec_name: Mapped[str] = mapped_column(String(128), nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    train_metrics: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    val_metrics: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    gatekeeper_results: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    gatekeeper_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verdict: Mapped[str] = mapped_column(
        String(64), nullable=False, default="PENDING"
    )  # PASSED | REJECTED_OVERFIT | REJECTED_CORRELATION | REJECTED_COST | REJECTED_SAMPLE | REJECTED_ROBUSTNESS | PROMOTED | REJECTED_MANUAL
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    human_decision: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_REVIEW"
    )  # PENDING_REVIEW | APPROVED | REJECTED
    human_decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class HoldoutAccessLog(Base):
    """Audit log of any authorization and access to the locked Holdout partition."""

    __tablename__ = "holdout_access_logs"
    __table_args__ = (Index("ix_holdout_access_logs_family", "family"),)

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ECBExchangeRate(Base):
    """Daily European Central Bank (ECB) official currency reference rates (Phase 9)."""

    __tablename__ = "ecb_exchange_rates"
    __table_args__ = (
        PrimaryKeyConstraint("rate_date", "base_currency", "target_currency"),
        Index("ix_ecb_rates_date", "rate_date"),
    )

    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    target_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class TaxLot(Base):
    """Individual tax lot tracked strictly by First-In-First-Out (FIFO) under § 20 EStG (Phase 9)."""

    __tablename__ = "tax_lots"
    __table_args__ = (
        Index("ix_tax_lots_symbol", "symbol"),
        Index("ix_tax_lots_status", "status"),
        Index("ix_tax_lots_buy_date", "buy_date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AKTIEN"
    )  # AKTIEN | SONSTIGE
    buy_fill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    buy_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity_initial: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity_remaining: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buy_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    buy_fx_rate_eur_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    buy_price_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_cost_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    commission_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN | PARTIAL | CLOSED
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class TaxEvent(Base):
    """Realized capital gain/loss taxable transaction with KESt and Solidaritätszuschlag (Phase 9)."""

    __tablename__ = "tax_events"
    __table_args__ = (
        Index("ix_tax_events_symbol", "symbol"),
        Index("ix_tax_events_tax_lot_id", "tax_lot_id"),
        Index("ix_tax_events_sell_date", "sell_date"),
        Index("ix_tax_events_tax_year", "tax_year"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tax_lot_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tax_lots.id"), nullable=False
    )
    sell_fill_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AKTIEN"
    )  # AKTIEN | SONSTIGE
    tax_year: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_date: Mapped[date] = mapped_column(Date, nullable=False)
    sell_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buy_price_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sell_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    sell_fx_rate_eur_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    sell_price_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    proceeds_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cost_basis_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    commission_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0")
    )
    gain_loss_eur: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    is_gain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kest_amount_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0")
    )
    soli_amount_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0")
    )
    kirchensteuer_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0")
    )
    total_tax_eur: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ShadowExecutionLog(Base):
    """Real-time tick-by-tick shadow trade execution & slippage telemetry (Phase 9)."""

    __tablename__ = "shadow_execution_logs"
    __table_args__ = (
        Index("ix_shadow_logs_run_id", "run_id"),
        Index("ix_shadow_logs_symbol", "symbol"),
        Index("ix_shadow_logs_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    broker_bid_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    broker_ask_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    broker_mid_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    simulated_fill_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    slippage_bps: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0.0")
    )
    quote_latency_ms: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.0")
    )
    routing_venue: Mapped[str] = mapped_column(String(32), nullable=False, default="SHADOW_SIM")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
