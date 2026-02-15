"""style scores and recommendations

Revision ID: 0003_style_tables
Revises: 0002_catalog_requests
Create Date: 2026-02-15 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_style_tables"
down_revision: Union[str, None] = "0002_catalog_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Align with Supabase schema: catalog_requests.image_path
    op.add_column("catalog_requests", sa.Column("image_path", sa.Text(), nullable=True))

    op.create_table(
        "style_scores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=36),
            sa.ForeignKey("catalog_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("image_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("casual", sa.Float(), nullable=True),
        sa.Column("minimal", sa.Float(), nullable=True),
        sa.Column("structured", sa.Float(), nullable=True),
        sa.Column("classic", sa.Float(), nullable=True),
        sa.Column("neutral", sa.Float(), nullable=True),
    )
    op.create_index("ix_style_scores_request_id", "style_scores", ["request_id"])

    op.create_table(
        "style_recommendations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=36),
            sa.ForeignKey("catalog_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("product_url", sa.String(length=2048), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("price_text", sa.String(length=128), nullable=True),
        sa.Column("price_value", sa.Float(), nullable=True),
        sa.Column("query_used", sa.Text(), nullable=True),
        sa.Column("recommendation_image_url", sa.String(length=2048), nullable=True),
        sa.Column("recommendation_image_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
    )
    op.create_index("ix_style_recommendations_request_id", "style_recommendations", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_style_recommendations_request_id", table_name="style_recommendations")
    op.drop_table("style_recommendations")
    op.drop_index("ix_style_scores_request_id", table_name="style_scores")
    op.drop_table("style_scores")
    op.drop_column("catalog_requests", "image_path")

