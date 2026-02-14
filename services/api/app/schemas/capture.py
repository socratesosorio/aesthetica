from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CaptureQueuedResponse(BaseModel):
    capture_id: str
    status: str


class GarmentOut(BaseModel):
    id: str
    garment_type: str
    crop_path: str
    attributes: dict


class MatchOut(BaseModel):
    id: str
    garment_id: str | None
    product_id: str
    rank: int
    similarity: float
    match_group: str


class CaptureOut(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    image_path: str
    status: str
    error: str | None
    global_attributes: dict | None
    garments: list[GarmentOut]
    matches: list[MatchOut]
