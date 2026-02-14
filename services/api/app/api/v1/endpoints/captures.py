from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import capture_rate_limiter
from app.models import Capture, User
from app.schemas.capture import CaptureOut, CaptureQueuedResponse, GarmentOut, MatchOut
from app.services.captures import create_capture
from app.workers.celery_app import celery_app

router = APIRouter()


@router.post("/captures", response_model=CaptureQueuedResponse)
def upload_capture(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaptureQueuedResponse:
    if not capture_rate_limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Capture rate limit exceeded")

    data = image.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image payload")

    capture = create_capture(db, user.id, data)
    celery_app.send_task("worker.tasks.process_capture", args=[capture.id])
    return CaptureQueuedResponse(capture_id=capture.id, status="queued")


@router.get("/captures/{capture_id}", response_model=CaptureOut)
def get_capture(
    capture_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaptureOut:
    cap = db.query(Capture).filter(Capture.id == capture_id, Capture.user_id == user.id).first()
    if cap is None:
        raise HTTPException(status_code=404, detail="Capture not found")

    garments = [
        GarmentOut(
            id=g.id,
            garment_type=g.garment_type,
            crop_path=g.crop_path,
            attributes=g.attributes_json,
        )
        for g in cap.garments
    ]
    matches = [
        MatchOut(
            id=m.id,
            garment_id=m.garment_id,
            product_id=m.product_id,
            rank=m.rank,
            similarity=m.similarity,
            match_group=m.match_group,
        )
        for m in cap.matches
    ]

    return CaptureOut(
        id=cap.id,
        user_id=cap.user_id,
        created_at=cap.created_at,
        image_path=cap.image_path,
        status=cap.status,
        error=cap.error,
        global_attributes=cap.global_attributes_json,
        garments=garments,
        matches=matches,
    )


@router.get("/users/{user_id}/captures", response_model=list[CaptureOut])
def user_captures(
    user_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CaptureOut]:
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    rows = (
        db.query(Capture)
        .filter(Capture.user_id == user_id)
        .order_by(Capture.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    out: list[CaptureOut] = []
    for cap in rows:
        out.append(
            CaptureOut(
                id=cap.id,
                user_id=cap.user_id,
                created_at=cap.created_at,
                image_path=cap.image_path,
                status=cap.status,
                error=cap.error,
                global_attributes=cap.global_attributes_json,
                garments=[
                    GarmentOut(
                        id=g.id,
                        garment_type=g.garment_type,
                        crop_path=g.crop_path,
                        attributes=g.attributes_json,
                    )
                    for g in cap.garments
                ],
                matches=[
                    MatchOut(
                        id=m.id,
                        garment_id=m.garment_id,
                        product_id=m.product_id,
                        rank=m.rank,
                        similarity=m.similarity,
                        match_group=m.match_group,
                    )
                    for m in cap.matches
                ],
            )
        )
    return out
