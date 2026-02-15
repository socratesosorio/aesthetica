from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import CatalogRecommendation, CatalogRequest, User
from app.schemas.catalog import CatalogFromImageResponse, CatalogRecommendationOut, CatalogRequestOut
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

    Returns recommendations for the most recent `catalog_recommendations` timestamp.
    (The table has a `timestamp` column; recommendations are grouped by `request_id`.)
    (Requests/recommendations are not user-scoped yet in the schema.)
    """
    del user

    latest_row = db.query(CatalogRecommendation).order_by(CatalogRecommendation.timestamp.desc()).first()
    if latest_row is None:
        return []

    rows = (
        db.query(CatalogRecommendation)
        .filter(CatalogRecommendation.request_id == latest_row.request_id)
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


@router.get("/catalog/requests", response_model=list[CatalogRequestOut])
def list_catalog_requests(
    limit: int = Query(default=24, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CatalogRequestOut]:
    """
    Read-only list of recent `catalog_requests`, for rendering "last captured" images.

    Note: this table is not user-scoped in the schema yet, so we return the most recent rows globally.
    """
    del user
    rows = db.query(CatalogRequest).order_by(CatalogRequest.created_at.desc()).limit(limit).all()
    return [
        CatalogRequestOut(
            id=r.id,
            created_at=r.created_at,
            image_path=r.image_path,
            pipeline_status=r.pipeline_status,
            garment_name=r.garment_name,
            brand_hint=r.brand_hint,
            confidence=r.confidence,
            error=r.error,
        )
        for r in rows
    ]


@router.get("/catalog/requests/{request_id}", response_model=CatalogRequestOut)
def get_catalog_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CatalogRequestOut:
    """
    Fetch a single catalog request by id (used for share links to older captures).
    """
    del user
    row = db.query(CatalogRequest).filter(CatalogRequest.id == request_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Catalog request not found")

    return CatalogRequestOut(
        id=row.id,
        created_at=row.created_at,
        image_path=row.image_path,
        pipeline_status=row.pipeline_status,
        garment_name=row.garment_name,
        brand_hint=row.brand_hint,
        confidence=row.confidence,
        error=row.error,
    )
