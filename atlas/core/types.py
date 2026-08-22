"""Core frozen domain models, enums, and identifier types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import NewType

from atlas.core.money import Money

Symbol = NewType("Symbol", str)
BrokerOrderRef = NewType("BrokerOrderRef", str)
Price = Decimal
Quantity = int


class BucketId(StrEnum):
    CORE = "CORE"
    SWING = "SWING"
    MOONSHOT = "MOONSHOT"
    CASH = "CASH"


class SignalLayer(StrEnum):
    L1_TECHNICAL = "L1_TECHNICAL"
    L2_STATISTICAL = "L2_STATISTICAL"
    L3_FUNDAMENTAL = "L3_FUNDAMENTAL"
    L4_NARRATIVE = "L4_NARRATIVE"


class RunMode(StrEnum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIVE = "LIVE"


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(StrEnum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class OrderStatus(StrEnum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class Bar:
    """Historical OHLCV bar. Timestamps must be tz-aware UTC and represent bar CLOSE."""

    symbol: Symbol
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adj_factor: Decimal = Decimal("1.0")
    vwap: Decimal | None = None
    source: str = "primary"
    resolution: str = "1d"

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError(f"Bar timestamp must be timezone-aware UTC: {self.ts}")
        if self.high < self.low:
            raise ValueError(f"Bar high ({self.high}) cannot be less than low ({self.low})")
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"Bar open ({self.open}) must be within [low ({self.low}), high ({self.high})]"
            )
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"Bar close ({self.close}) must be within [low ({self.low}), high ({self.high})]"
            )


@dataclass(frozen=True, slots=True)
class Signal:
    """Point-in-time alpha signal produced by a SignalProvider."""

    provider: str
    layer: SignalLayer
    symbol: Symbol
    ts: datetime
    score: float  # [-1.0 .. 1.0]
    confidence: float  # [0.0 .. 1.0]
    rationale: str = ""
    features: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Signal timestamp must be timezone-aware UTC")
        if not (-1.0 <= self.score <= 1.0):
            raise ValueError(f"Signal score must be within [-1.0, 1.0], got {self.score}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Signal confidence must be within [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class Order:
    """Trading order requested or submitted."""

    id: str
    run_id: str
    strategy_version_id: str
    bucket: BucketId
    symbol: Symbol
    side: Side
    qty: Quantity
    type: OrderType
    tif: TimeInForce
    created_ts: datetime
    limit_px: Decimal | None = None
    stop_px: Decimal | None = None
    status: OrderStatus = OrderStatus.NEW
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.created_ts.tzinfo is None:
            raise ValueError("Order created_ts must be timezone-aware UTC")
        if self.qty <= 0:
            raise ValueError(f"Order quantity must be positive: {self.qty}")


@dataclass(frozen=True, slots=True)
class Fill:
    """Execution fill report from a broker."""

    order_id: str
    ts: datetime
    qty: Quantity
    price: Decimal
    commission: Money
    fees: Money
    slippage_est: Money
    venue: str

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Fill timestamp must be timezone-aware UTC")
        if self.qty <= 0:
            raise ValueError(f"Fill quantity must be positive: {self.qty}")


@dataclass(frozen=True, slots=True)
class Position:
    """Current open position state."""

    symbol: Symbol
    bucket: BucketId
    qty: Quantity
    avg_price: Decimal
    opened_ts: datetime
    unrealized: Money
    realized: Money
    stop_px: Decimal | None = None

    def __post_init__(self) -> None:
        if self.opened_ts.tzinfo is None:
            raise ValueError("Position opened_ts must be timezone-aware UTC")


@dataclass(frozen=True, slots=True)
class AccountState:
    """Overall account snapshot."""

    ts: datetime
    total_equity: Money
    cash: Money
    buying_power: Money
    per_bucket_equity: dict[BucketId, Money]


@dataclass(frozen=True, slots=True)
class NewsItem:
    """Point-in-time published news item."""

    id: str
    ts: datetime
    source: str
    symbols: tuple[Symbol, ...]
    title: str
    body: str
    url: str


@dataclass(frozen=True, slots=True)
class FundamentalSnapshot:
    """Point-in-time fundamental filing record."""

    symbol: Symbol
    report_date: datetime
    filing_date: datetime
    period: str
    metrics: dict[str, float]
