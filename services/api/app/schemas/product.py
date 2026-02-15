from __future__ import annotations

from pydantic import BaseModel


class ProductSearchOut(BaseModel):
    product_id: str
    title: str
    brand: str
    category: str
    price: float | None
    currency: str | None
    image_url: str | None = None
    source: str | None = None
    product_url: str
    similarity: float
    rank: int


class ProductRecommendationOut(BaseModel):
    product_id: str
    title: str
    brand: str
    category: str
    price: float | None
    currency: str | None
    image_url: str | None = None
    product_url: str
    reason: str | None = None
    score: float | None = None
