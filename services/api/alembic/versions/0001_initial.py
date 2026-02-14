"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-14 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "captures",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("image_path", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("global_attributes_json", sa.JSON(), nullable=True),
        sa.Column("global_embedding", sa.LargeBinary(), nullable=True),
    )
    op.create_index("ix_captures_user_id", "captures", ["user_id"])

    op.create_table(
        "garments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("capture_id", sa.String(length=36), sa.ForeignKey("captures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("garment_type", sa.String(length=32), nullable=False),
        sa.Column("crop_path", sa.String(length=512), nullable=False),
        sa.Column("embedding_vector", sa.LargeBinary(), nullable=True),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_garments_capture_id", "garments", ["capture_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("product_url", sa.String(length=1024), nullable=False),
        sa.Column("color_tags", sa.JSON(), nullable=True),
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("capture_id", sa.String(length=36), sa.ForeignKey("captures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("garment_id", sa.String(length=36), sa.ForeignKey("garments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", sa.String(length=64), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=False),
        sa.Column("match_group", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_matches_capture_id", "matches", ["capture_id"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding_vector", sa.LargeBinary(), nullable=True),
        sa.Column("radar_vector_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("brand_stats", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("color_stats", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("category_bias", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user_radar_history",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("radar_vector_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_user_radar_history_user_id", "user_radar_history", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_radar_history_user_id", table_name="user_radar_history")
    op.drop_table("user_radar_history")
    op.drop_table("user_profiles")
    op.drop_index("ix_matches_capture_id", table_name="matches")
    op.drop_table("matches")
    op.drop_table("products")
    op.drop_index("ix_garments_capture_id", table_name="garments")
    op.drop_table("garments")
    op.drop_index("ix_captures_user_id", table_name="captures")
    op.drop_table("captures")
    op.drop_table("users")
