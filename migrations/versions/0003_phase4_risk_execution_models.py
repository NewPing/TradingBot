"""Phase 4 schema: orders, fills, positions_snapshots, and kill_switch_events.

Revision ID: 0003_phase4_risk_execution_models
Revises: 0002_phase3_versioning_runs_trials
Create Date: 2026-08-23 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_phase4_risk_execution_models"
down_revision: str | Sequence[str] | None = "0002_phase3_versioning_runs_trials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column(
            "strategy_version_id",
            sa.String(length=64),
            sa.ForeignKey("strategy_versions.id"),
            nullable=False,
        ),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.BigInteger(), nullable=False),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("tif", sa.String(length=16), nullable=False, server_default="DAY"),
        sa.Column("limit_px", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("stop_px", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="NEW"),
        sa.Column("broker_ref", sa.String(length=128), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_run_id", "orders", ["run_id"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_status", "orders", ["status"])

    # 2. fills table
    op.create_table(
        "fills",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("order_id", sa.String(length=64), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("qty", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "commission",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "fees",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "slippage_est",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0",
        ),
        sa.Column("venue", sa.String(length=32), nullable=False, server_default="ALPACA_PAPER"),
    )
    op.create_index("ix_fills_order_id", "fills", ["order_id"])
    op.create_index("ix_fills_ts", "fills", ["ts"])

    # 3. positions_snapshots table
    op.create_table(
        "positions_snapshots",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("qty", sa.BigInteger(), nullable=False),
        sa.Column("avg_price", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("market_value", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(precision=18, scale=4), nullable=False),
    )
    op.create_index("ix_positions_snapshots_run_id_ts", "positions_snapshots", ["run_id", "ts"])

    # 4. kill_switch_events table
    op.create_table(
        "kill_switch_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kill_switch_events_ts", "kill_switch_events", ["ts"])
    op.create_index("ix_kill_switch_events_trigger", "kill_switch_events", ["trigger"])


def downgrade() -> None:
    op.drop_table("kill_switch_events")
    op.drop_table("positions_snapshots")
    op.drop_table("fills")
    op.drop_table("orders")
