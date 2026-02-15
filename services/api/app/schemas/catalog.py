from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CatalogRecommendationOut(BaseModel):
    rank: int
    title: str
    product_url: str
    source: str | None = None
    price_text: str | None = None
    price_value: float | None = None
    query_used: str | None = None
    recommendation_image_url: str | None = None
    has_recommendation_image_bytes: bool


class CatalogFromImageResponse(BaseModel):
    request_id: str
    created_at: datetime
    pipeline_status: str
    garment_name: str | None = None
    brand_hint: str | None = None
    confidence: float | None = None
    error: str | None = None
    recommendation_count: int
    recommendations: list[CatalogRecommendationOut]
