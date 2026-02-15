from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StyleScoreOut(BaseModel):
    id: str
    request_id: str
    created_at: datetime
    description: str | None = None
    has_image_bytes: bool
    casual: float | None = None
    minimal: float | None = None
    structured: float | None = None
    classic: float | None = None
    neutral: float | None = None


class StyleRecommendationOut(BaseModel):
    rank: int
    title: str
    product_url: str
    source: str | None = None
    price_text: str | None = None
    price_value: float | None = None
    query_used: str | None = None
    recommendation_image_url: str | None = None
    has_recommendation_image_bytes: bool
    rationale: str | None = None

