from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    captures: Mapped[list["Capture"]] = relationship(back_populates="user")
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False)


class Capture(Base):
    __tablename__ = "captures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    global_attributes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    global_embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    user: Mapped[User] = relationship(back_populates="captures")
    garments: Mapped[list["Garment"]] = relationship(back_populates="capture", cascade="all, delete-orphan")
    matches: Mapped[list["Match"]] = relationship(back_populates="capture", cascade="all, delete-orphan")


class Garment(Base):
    __tablename__ = "garments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    capture_id: Mapped[str] = mapped_column(ForeignKey("captures.id", ondelete="CASCADE"), index=True)
    garment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    crop_path: Mapped[str] = mapped_column(String(512), nullable=False)
    embedding_vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    attributes_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    capture: Mapped[Capture] = relationship(back_populates="garments")
    matches: Mapped[list["Match"]] = relationship(back_populates="garment")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    color_tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    capture_id: Mapped[str] = mapped_column(ForeignKey("captures.id", ondelete="CASCADE"), index=True)
    garment_id: Mapped[str | None] = mapped_column(ForeignKey("garments.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    match_group: Mapped[str] = mapped_column(String(32), nullable=False)

    capture: Mapped[Capture] = relationship(back_populates="matches")
    garment: Mapped[Garment | None] = relationship(back_populates="matches")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    embedding_vector: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    radar_vector_json: Mapped[dict] = mapped_column(JSON, default=dict)
    brand_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    color_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    category_bias: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="profile")


class UserRadarHistory(Base):
    __tablename__ = "user_radar_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    radar_vector_json: Mapped[dict] = mapped_column(JSON, nullable=False)
