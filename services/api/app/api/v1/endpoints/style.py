from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import CatalogRequest, StyleRecommendation, StyleScore, User
from app.schemas.style import StyleRecommendationOut, StyleScoreOut

router = APIRouter()


@router.get("/style/scores", response_model=list[StyleScoreOut])
def list_style_scores(
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StyleScoreOut]:
    """
    Read-only view of `style_scores` for graphing.

    Note: this table is not user-scoped in the schema yet, so we return the most recent rows globally.
    """
    del user
    rows = db.query(StyleScore).order_by(StyleScore.created_at.desc()).limit(limit).all()
    return [
        StyleScoreOut(
            id=r.id,
            request_id=r.request_id,
            created_at=r.created_at,
            description=r.description,
            has_image_bytes=bool(r.image_bytes),
            casual=r.casual,
            minimal=r.minimal,
            structured=r.structured,
            classic=r.classic,
            neutral=r.neutral,
        )
        for r in rows
    ]


@router.get("/style/recommendations", response_model=list[StyleRecommendationOut])
def latest_style_recommendations(
    limit: int = Query(default=24, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StyleRecommendationOut]:
    """
    Recommended-for-you based on overall style trends.

    Return the most recent `style_recommendations` set (by created_at), grouped by request_id.

    To reduce confusion with "last capture" recommendations, we try to avoid returning the same
    `catalog_requests.id` that backs the latest capture-driven catalog recommendations.
    """
    del user

    latest_capture_req = db.query(CatalogRequest).order_by(CatalogRequest.created_at.desc()).first()
    exclude_request_id = latest_capture_req.id if latest_capture_req else None

    latest_row = (
        db.query(StyleRecommendation)
        .filter(StyleRecommendation.request_id != exclude_request_id)  # type: ignore[arg-type]
        .order_by(StyleRecommendation.created_at.desc())
        .first()
    )
    if latest_row is None:
        # Fallback: if there's only one request_id in the table, return it.
        latest_row = db.query(StyleRecommendation).order_by(StyleRecommendation.created_at.desc()).first()
    if latest_row is None:
        return []

    rows = (
        db.query(StyleRecommendation)
        .filter(StyleRecommendation.request_id == latest_row.request_id)
        .order_by(StyleRecommendation.rank.asc())
        .limit(limit)
        .all()
    )
    return [
        StyleRecommendationOut(
            rank=r.rank,
            title=r.title,
            product_url=r.product_url,
            source=r.source,
            price_text=r.price_text,
            price_value=r.price_value,
            query_used=r.query_used,
            recommendation_image_url=r.recommendation_image_url,
            has_recommendation_image_bytes=bool(r.recommendation_image_bytes),
            rationale=r.rationale,
        )
        for r in rows
    ]

