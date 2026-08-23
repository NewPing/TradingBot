"""Phase 8 schema: research_hypotheses, research_sweeps, research_reports, and holdout_access_logs.

Revision ID: 0006_phase8_research_loop
Revises: 0005_phase7_news_llm_signals
Create Date: 2026-08-23 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_phase8_research_loop"
down_revision: str | Sequence[str] | None = "0005_phase7_news_llm_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. research_hypotheses
    op.create_table(
        "research_hypotheses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("generator_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("base_spec_name", sa.String(length=128), nullable=False),
        sa.Column("proposed_spec", sa.Text(), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "prior_score",
            sa.Numeric(precision=10, scale=4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_hypotheses_family", "research_hypotheses", ["family"], unique=False
    )
    op.create_index(
        "ix_research_hypotheses_status", "research_hypotheses", ["status"], unique=False
    )
    op.create_index(
        "ix_research_hypotheses_generator",
        "research_hypotheses",
        ["generator_type"],
        unique=False,
    )

    # 2. research_sweeps
    op.create_table(
        "research_sweeps",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=64), nullable=True),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("sweep_type", sa.String(length=32), nullable=False, server_default="GRID"),
        sa.Column("param_grid", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("total_combinations", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_combinations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_candidate_params", sa.Text(), nullable=True),
        sa.Column(
            "best_metric_name",
            sa.String(length=64),
            nullable=False,
            server_default="sharpe_ratio",
        ),
        sa.Column("best_metric_value", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["research_hypotheses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_sweeps_hypothesis_id", "research_sweeps", ["hypothesis_id"], unique=False
    )
    op.create_index("ix_research_sweeps_family", "research_sweeps", ["family"], unique=False)
    op.create_index("ix_research_sweeps_status", "research_sweeps", ["status"], unique=False)

    # 3. research_reports
    op.create_table(
        "research_reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("strategy_spec_name", sa.String(length=128), nullable=False),
        sa.Column("spec_hash", sa.String(length=64), nullable=False),
        sa.Column("train_metrics", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("val_metrics", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("gatekeeper_results", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "gatekeeper_passed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("verdict", sa.String(length=64), nullable=False, server_default="PENDING"),
        sa.Column("report_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "human_decision",
            sa.String(length=32),
            nullable=False,
            server_default="PENDING_REVIEW",
        ),
        sa.Column("human_decision_notes", sa.Text(), nullable=True),
        sa.Column("human_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["research_hypotheses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_reports_hypothesis_id", "research_reports", ["hypothesis_id"], unique=False
    )
    op.create_index("ix_research_reports_family", "research_reports", ["family"], unique=False)
    op.create_index("ix_research_reports_verdict", "research_reports", ["verdict"], unique=False)
    op.create_index(
        "ix_research_reports_human_decision",
        "research_reports",
        ["human_decision"],
        unique=False,
    )

    # 4. holdout_access_logs
    op.create_table(
        "holdout_access_logs",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("unlocked_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=True),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_holdout_access_logs_family", "holdout_access_logs", ["family"], unique=False
    )


def downgrade() -> None:
    op.drop_table("holdout_access_logs")
    op.drop_table("research_reports")
    op.drop_table("research_sweeps")
    op.drop_table("research_hypotheses")
