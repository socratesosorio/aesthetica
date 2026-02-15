from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import CatalogRecommendation, CatalogRequest, User
from app.schemas.catalog import CatalogFromImageResponse, CatalogRecommendationOut
from app.services.catalog_from_image import process_catalog_from_image

router = APIRouter()


@router.post("/catalog/from-image", response_model=CatalogFromImageResponse)
async def catalog_from_image(
    request: Request,
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> CatalogFromImageResponse:
    payload: bytes
    filename: str | None = None
    content_type: str | None = None
    if image is not None:
        payload = image.file.read()
        filename = image.filename
        content_type = image.content_type or "application/octet-stream"
    else:
        payload = await request.body()
        content_type = request.headers.get("content-type", "application/octet-stream")

    if not payload:
        raise HTTPException(status_code=400, detail="Empty image payload")
    if not (content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")

    return process_catalog_from_image(
        db=db,
        image_bytes=payload,
        filename=filename,
        content_type=content_type,
    )


@router.get("/catalog/recommendations", response_model=list[CatalogRecommendationOut])
def latest_catalog_recommendations(
    limit: int = Query(default=24, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CatalogRecommendationOut]:
    """
    Read-only feed backed by `catalog_recommendations`.

    Currently returns recommendations for the most recent `catalog_requests` row.
    (Requests/recommendations are not user-scoped yet in the schema.)
    """
    del user

    req = db.query(CatalogRequest).order_by(CatalogRequest.created_at.desc()).first()
    if req is None:
        return []

    rows = (
        db.query(CatalogRecommendation)
        .filter(CatalogRecommendation.request_id == req.id)
        .order_by(CatalogRecommendation.rank.asc())
        .limit(limit)
        .all()
    )
    return [
        CatalogRecommendationOut(
            rank=r.rank,
            title=r.title,
            product_url=r.product_url,
            source=r.source,
            price_text=r.price_text,
            price_value=r.price_value,
            query_used=r.query_used,
            recommendation_image_url=r.recommendation_image_url,
            has_recommendation_image_bytes=bool(r.recommendation_image_bytes),
        )
        for r in rows
    ]
