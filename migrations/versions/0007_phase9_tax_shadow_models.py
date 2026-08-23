"""Phase 9 schema: ecb_exchange_rates, tax_lots, tax_events, and shadow_execution_logs.

Revision ID: 0007_phase9_tax_shadow_models
Revises: 0006_phase8_research_loop
Create Date: 2026-08-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_phase9_tax_shadow_models"
down_revision: str | Sequence[str] | None = "0006_phase8_research_loop"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. ecb_exchange_rates
    op.create_table(
        "ecb_exchange_rates",
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("target_currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("rate", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("rate_date", "base_currency", "target_currency"),
    )
    op.create_index("ix_ecb_rates_date", "ecb_exchange_rates", ["rate_date"], unique=False)

    # 2. tax_lots
    op.create_table(
        "tax_lots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("asset_category", sa.String(length=32), nullable=False, server_default="AKTIEN"),
        sa.Column("buy_fill_id", sa.String(length=64), nullable=True),
        sa.Column("buy_date", sa.Date(), nullable=False),
        sa.Column("buy_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity_initial", sa.BigInteger(), nullable=False),
        sa.Column("quantity_remaining", sa.BigInteger(), nullable=False),
        sa.Column("buy_price_usd", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("buy_fx_rate_eur_usd", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("buy_price_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("total_cost_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "commission_eur",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tax_lots_symbol", "tax_lots", ["symbol"], unique=False)
    op.create_index("ix_tax_lots_status", "tax_lots", ["status"], unique=False)
    op.create_index("ix_tax_lots_buy_date", "tax_lots", ["buy_date"], unique=False)

    # 3. tax_events
    op.create_table(
        "tax_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tax_lot_id", sa.String(length=64), nullable=False),
        sa.Column("sell_fill_id", sa.String(length=64), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("asset_category", sa.String(length=32), nullable=False, server_default="AKTIEN"),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("sell_date", sa.Date(), nullable=False),
        sa.Column("sell_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("buy_price_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("sell_price_usd", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("sell_fx_rate_eur_usd", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("sell_price_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("proceeds_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("cost_basis_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "commission_eur",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column("gain_loss_eur", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("is_gain", sa.Boolean(), nullable=False),
        sa.Column(
            "kest_amount_eur",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "soli_amount_eur",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "kirchensteuer_eur",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "total_tax_eur",
            sa.Numeric(precision=18, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tax_lot_id"], ["tax_lots.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tax_events_symbol", "tax_events", ["symbol"], unique=False)
    op.create_index("ix_tax_events_tax_lot_id", "tax_events", ["tax_lot_id"], unique=False)
    op.create_index("ix_tax_events_sell_date", "tax_events", ["sell_date"], unique=False)
    op.create_index("ix_tax_events_tax_year", "tax_events", ["tax_year"], unique=False)

    # 4. shadow_execution_logs
    op.create_table(
        "shadow_execution_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("model_price_usd", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("broker_bid_usd", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("broker_ask_usd", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("broker_mid_usd", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("simulated_fill_price_usd", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "slippage_bps", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0.0"
        ),
        sa.Column(
            "quote_latency_ms",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "routing_venue", sa.String(length=32), nullable=False, server_default="SHADOW_SIM"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shadow_logs_run_id", "shadow_execution_logs", ["run_id"], unique=False)
    op.create_index("ix_shadow_logs_symbol", "shadow_execution_logs", ["symbol"], unique=False)
    op.create_index(
        "ix_shadow_logs_timestamp", "shadow_execution_logs", ["timestamp"], unique=False
    )


def downgrade() -> None:
    op.drop_table("shadow_execution_logs")
    op.drop_table("tax_events")
    op.drop_table("tax_lots")
    op.drop_table("ecb_exchange_rates")
