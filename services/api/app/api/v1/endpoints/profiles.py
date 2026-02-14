from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User, UserProfile, UserRadarHistory
from app.schemas.profile import RadarHistoryPoint, UserProfileOut

router = APIRouter()


@router.get("/users/{user_id}/profile", response_model=UserProfileOut)
def get_profile(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserProfileOut:
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        return UserProfileOut(
            user_id=user_id,
            user_embedding_meta={"dim": 512, "initialized": False},
            radar_vector={},
            brand_stats={},
            color_stats={},
            category_bias={},
            updated_at=None,
        )

    return UserProfileOut(
        user_id=user_id,
        user_embedding_meta={"dim": 512, "initialized": bool(profile.embedding_vector)},
        radar_vector=profile.radar_vector_json or {},
        brand_stats=profile.brand_stats or {},
        color_stats=profile.color_stats or {},
        category_bias=profile.category_bias or {},
        updated_at=profile.updated_at,
    )


@router.get("/users/{user_id}/radar/history", response_model=list[RadarHistoryPoint])
def radar_history(
    user_id: str,
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[RadarHistoryPoint]:
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))
    rows = (
        db.query(UserRadarHistory)
        .filter(UserRadarHistory.user_id == user_id, UserRadarHistory.created_at >= cutoff)
        .order_by(UserRadarHistory.created_at.asc())
        .all()
    )
    return [RadarHistoryPoint(id=r.id, created_at=r.created_at, radar_vector=r.radar_vector_json) for r in rows]
