"""add generated_product_image_url to catalog_requests

Revision ID: 0005_generated_product_image_url
Revises: 0004_catalog_recommendations_timestamp
Create Date: 2026-02-15 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0005_generated_product_image_url"
down_revision: tuple = ("0004_catalog_recommendations_timestamp", "0003_style_scores_recs")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("catalog_requests")}
    if "generated_product_image_url" not in cols:
        op.add_column(
            "catalog_requests",
            sa.Column("generated_product_image_url", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("catalog_requests")}
    if "generated_product_image_url" in cols:
        op.drop_column("catalog_requests", "generated_product_image_url")
