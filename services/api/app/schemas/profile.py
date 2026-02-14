from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserProfileOut(BaseModel):
    user_id: str
    user_embedding_meta: dict
    radar_vector: dict
    brand_stats: dict
    color_stats: dict
    category_bias: dict
    updated_at: datetime | None


class RadarHistoryPoint(BaseModel):
    id: str
    created_at: datetime
    radar_vector: dict
