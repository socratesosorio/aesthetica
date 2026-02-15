"""catalog requests and recommendations

Revision ID: 0002_catalog_requests
Revises: 0001_initial
Create Date: 2026-02-15 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_catalog_requests"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("original_content_type", sa.String(length=128), nullable=True),
        sa.Column("original_image_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("pipeline_status", sa.String(length=64), nullable=False, server_default="processing"),
        sa.Column("garment_name", sa.String(length=64), nullable=True),
        sa.Column("brand_hint", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "catalog_recommendations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("request_id", sa.String(length=36), sa.ForeignKey("catalog_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("product_url", sa.String(length=2048), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("price_text", sa.String(length=128), nullable=True),
        sa.Column("price_value", sa.Float(), nullable=True),
        sa.Column("query_used", sa.Text(), nullable=True),
        sa.Column("recommendation_image_url", sa.String(length=2048), nullable=True),
        sa.Column("recommendation_image_bytes", sa.LargeBinary(), nullable=True),
    )
    op.create_index("ix_catalog_recommendations_request_id", "catalog_recommendations", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_recommendations_request_id", table_name="catalog_recommendations")
    op.drop_table("catalog_recommendations")
    op.drop_table("catalog_requests")
