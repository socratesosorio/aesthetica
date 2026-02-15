from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.catalog import CatalogFromImageResponse
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
