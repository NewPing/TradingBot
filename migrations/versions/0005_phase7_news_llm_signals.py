"""Phase 7 schema: news_articles, news_scores, and prompt_templates.

Revision ID: 0005_phase7_news_llm_signals
Revises: 0004_phase6_fundamentals_earnings
Create Date: 2026-08-23 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_phase7_news_llm_signals"
down_revision: str | Sequence[str] | None = "0004_phase6_fundamentals_earnings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. news_articles
    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="alpaca_news"),
        sa.Column("url", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symbols", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"])
    op.create_index("ix_news_articles_content_hash", "news_articles", ["content_hash"])
    op.create_index("ix_news_articles_source", "news_articles", ["source"])

    # 2. news_scores
    op.create_table(
        "news_scores",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("article_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("sentiment_score", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("relevance_score", sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column("horizon", sa.String(length=32), nullable=False, server_default="SHORT_TERM"),
        sa.Column(
            "novelty_score", sa.Numeric(precision=6, scale=4), nullable=False, server_default="0.5"
        ),
        sa.Column("impact", sa.String(length=16), nullable=False, server_default="NEUTRAL"),
        sa.Column(
            "confidence", sa.Numeric(precision=6, scale=4), nullable=False, server_default="0.8"
        ),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["article_id"], ["news_articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_scores_article_id", "news_scores", ["article_id"])
    op.create_index("ix_news_scores_prompt_version", "news_scores", ["prompt_version"])
    op.create_index("ix_news_scores_scored_at", "news_scores", ["scored_at"])

    # 3. prompt_templates
    op.create_table(
        "prompt_templates",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("schema_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prompt_templates_name_version", "prompt_templates", ["name", "version"], unique=True
    )
    op.create_index("ix_prompt_templates_hash", "prompt_templates", ["prompt_hash"])


def downgrade() -> None:
    op.drop_table("prompt_templates")
    op.drop_table("news_scores")
    op.drop_table("news_articles")
