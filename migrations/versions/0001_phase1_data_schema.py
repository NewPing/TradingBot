"""Initial Phase 1 data schema with instruments, bars_1d, universe_snapshots, corporate_actions, and data_health.

Revision ID: 0001_phase1_data_schema
Revises:
Create Date: 2026-08-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_phase1_data_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. instruments
    op.create_table(
        "instruments",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("exchange", sa.String(length=32), nullable=False, server_default="US"),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("listed_on", sa.Date(), nullable=True),
        sa.Column("delisted_on", sa.Date(), nullable=True),
        sa.Column("is_etf", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("adv_usd", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.PrimaryKeyConstraint("symbol"),
    )

    # 2. universe_snapshots
    op.create_table(
        "universe_snapshots",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("snapshot_date", "symbol"),
    )
    op.create_index("ix_universe_snapshots_date", "universe_snapshots", ["snapshot_date"])

    # 3. bars_1d
    op.create_table(
        "bars_1d",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column(
            "adj_factor",
            sa.Numeric(precision=18, scale=8),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("vwap", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="tiingo"),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )
    op.create_index("ix_bars_1d_symbol_ts", "bars_1d", ["symbol", "ts"])
    op.create_index("ix_bars_1d_ts", "bars_1d", ["ts"])

    # 4. corporate_actions
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("ratio", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_corporate_actions_symbol_ex_date", "corporate_actions", ["symbol", "ex_date"]
    )

    # 5. data_health
    op.create_table(
        "data_health",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("check_name", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_health_check_ts", "data_health", ["check_name", "ts"])
    op.create_index("ix_data_health_symbol", "data_health", ["symbol"])


def downgrade() -> None:
    op.drop_table("data_health")
    op.drop_table("corporate_actions")
    op.drop_table("bars_1d")
    op.drop_table("universe_snapshots")
    op.drop_table("instruments")
