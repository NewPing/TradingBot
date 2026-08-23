"""Phase 3 schema: strategy_versions, runs, run_metrics, equity_curve, run_trades, and trials.

Revision ID: 0002_phase3_versioning_runs_trials
Revises: 0001_phase1_data_schema
Create Date: 2026-08-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_phase3_versioning_runs_trials"
down_revision: str | Sequence[str] | None = "0001_phase1_data_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. strategy_versions
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("spec_yaml", sa.Text(), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("git_sha", sa.String(length=40), nullable=True),
        sa.Column(
            "parent_id", sa.String(length=64), sa.ForeignKey("strategy_versions.id"), nullable=True
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RESEARCH"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_versions_family", "strategy_versions", ["family"])
    op.create_index("ix_strategy_versions_spec_hash", "strategy_versions", ["spec_hash"])

    # 2. runs
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column(
            "strategy_version_id",
            sa.String(length=64),
            sa.ForeignKey("strategy_versions.id"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="BACKTEST"),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("universe_hash", sa.String(length=64), nullable=True),
        sa.Column("data_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False, server_default="42"),
        sa.Column("git_sha", sa.String(length=40), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("cost_model_hash", sa.String(length=64), nullable=False),
        sa.Column("lib_versions", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("summary_metrics", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_strategy_version_id", "runs", ["strategy_version_id"])
    op.create_index("ix_runs_status", "runs", ["status"])

    # 3. run_metrics
    op.create_table(
        "run_metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("window", sa.String(32), nullable=False, server_default="FULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_metrics_run_metric", "run_metrics", ["run_id", "metric_name"])

    # 4. equity_curve
    op.create_table(
        "equity_curve",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_equity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cash", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("per_bucket", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "drawdown", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_equity_curve_run_ts", "equity_curve", ["run_id", "ts"])

    # 5. run_trades
    op.create_table(
        "run_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("trade_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("pnl", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("pnl_net", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("return_pct", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("fees", sa.Numeric(precision=18, scale=4), nullable=False, server_default="0"),
        sa.Column(
            "slippage", sa.Numeric(precision=18, scale=4), nullable=False, server_default="0"
        ),
        sa.Column("exit_reason", sa.String(length=64), nullable=False, server_default="SIGNAL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_trades_run_id", "run_trades", ["run_id"])
    op.create_index("ix_run_trades_symbol", "run_trades", ["symbol"])

    # 6. trials
    op.create_table(
        "trials",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("hypothesis_id", sa.String(length=64), nullable=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("params", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("metrics", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trials_family", "trials", ["family"])
    op.create_index("ix_trials_run_id", "trials", ["run_id"])


def downgrade() -> None:
    op.drop_table("trials")
    op.drop_table("run_trades")
    op.drop_table("equity_curve")
    op.drop_table("run_metrics")
    op.drop_table("runs")
    op.drop_table("strategy_versions")
