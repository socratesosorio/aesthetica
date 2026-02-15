"""catalog_recommendations timestamp column

Revision ID: 0004_catalog_recommendations_timestamp
Revises: 0003_style_tables
Create Date: 2026-02-15 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "0004_catalog_recommendations_timestamp"
down_revision: Union[str, None] = "0003_style_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("catalog_recommendations")}
    if "timestamp" not in cols:
        op.add_column(
            "catalog_recommendations",
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("catalog_recommendations")}
    if "timestamp" in cols:
        op.drop_column("catalog_recommendations", "timestamp")

