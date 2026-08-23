"""Pydantic schemas for Run and Comparison API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunResponse(BaseModel):
    id: str
    strategy_version_id: str
    mode: str
    start_ts: datetime
    end_ts: datetime
    data_snapshot_id: str
    seed: int
    git_sha: str
    spec_hash: str
    cost_model_hash: str
    lib_versions: dict[str, str] = Field(default_factory=dict)
    status: str
    summary_metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    completed_at: datetime | None = None


class RunCreateRequest(BaseModel):
    strategy_version_id: str
    snapshot_path: str
    start_date: str | None = None
    end_date: str | None = None
    capital_usd: float = 100_000.0
    seed: int = 42


class EquityPointResponse(BaseModel):
    ts: datetime
    total_equity: float
    cash: float
    drawdown: float
    per_bucket: dict[str, Any] = Field(default_factory=dict)


class RunTradeResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_net: float
    return_pct: float
    fees: float
    slippage: float
    exit_reason: str


class CompareRequest(BaseModel):
    run_ids: list[str]


class CompareResponse(BaseModel):
    runs: list[dict[str, Any]]
    metrics_diff: dict[str, dict[str, float]]
    equity_by_run: dict[str, list[dict[str, Any]]]


class HorizonMetricsResponse(BaseModel):
    horizon: str
    start_date: str
    end_date: str
    trading_days: int
    starting_capital: float
    ending_equity: float
    net_profit_usd: float
    strategy_return_pct: float
    strategy_cagr: float
    strategy_sharpe: float
    strategy_sortino: float
    strategy_max_drawdown: float
    strategy_calmar: float
    win_rate: float
    profit_factor: float
    total_trades: int

    # Benchmark stats
    benchmark_starting_equity: float
    benchmark_ending_equity: float
    benchmark_profit_usd: float
    benchmark_return_pct: float
    benchmark_cagr: float
    benchmark_max_drawdown: float
    alpha: float
    beta: float
    information_ratio: float
    tracking_error: float
    correlation: float

    # Holding Durations & Frictional Drag (Turnover/Costs)
    avg_holding_days: float = 0.0
    avg_win_holding_days: float = 0.0
    avg_loss_holding_days: float = 0.0
    total_slippage_usd: float = 0.0
    total_commissions_usd: float = 0.0
    total_fees_usd: float = 0.0
    total_frictional_drag_usd: float = 0.0
    gross_profit_usd: float = 0.0
    frictional_drag_pct: float = 0.0
