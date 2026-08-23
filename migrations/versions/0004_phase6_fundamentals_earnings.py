"""Phase 6 schema: fundamentals_pit and earnings_events.

Revision ID: 0004_phase6_fundamentals_earnings
Revises: 0003_phase4_risk_execution_models
Create Date: 2026-08-23 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_phase6_fundamentals_earnings"
down_revision: str | Sequence[str] | None = "0003_phase4_risk_execution_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. fundamentals_pit table
    op.create_table(
        "fundamentals_pit",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("filing_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column(
            "statement_type",
            sa.String(length=32),
            nullable=False,
            server_default="INCOME_BALANCE_CASH",
        ),
        sa.Column("metrics", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_fundamentals_pit_symbol_filing",
        "fundamentals_pit",
        ["symbol", "filing_date"],
    )
    op.create_index(
        "ix_fundamentals_pit_filing_date",
        "fundamentals_pit",
        ["filing_date"],
    )
    op.create_index(
        "ix_fundamentals_pit_symbol_report",
        "fundamentals_pit",
        ["symbol", "report_date"],
    )

    # 2. earnings_events table
    op.create_table(
        "earnings_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("time_of_day", sa.String(length=16), nullable=False, server_default="AMC"),
        sa.Column("fiscal_period", sa.String(length=16), nullable=True),
        sa.Column("eps_estimated", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("eps_actual", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("revenue_estimated", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("revenue_actual", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_earnings_events_symbol_date",
        "earnings_events",
        ["symbol", "event_date"],
    )
    op.create_index(
        "ix_earnings_events_event_date",
        "earnings_events",
        ["event_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_earnings_events_event_date", table_name="earnings_events")
    op.drop_index("ix_earnings_events_symbol_date", table_name="earnings_events")
    op.drop_table("earnings_events")

    op.drop_index("ix_fundamentals_pit_symbol_report", table_name="fundamentals_pit")
    op.drop_index("ix_fundamentals_pit_filing_date", table_name="fundamentals_pit")
    op.drop_index("ix_fundamentals_pit_symbol_filing", table_name="fundamentals_pit")
    op.drop_table("fundamentals_pit")
