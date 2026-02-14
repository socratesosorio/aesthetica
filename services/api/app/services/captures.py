from __future__ import annotations

import logging
import uuid
from io import BytesIO

from PIL import Image
from sqlalchemy.orm import Session

from app.models import Capture
from ml_core.storage import get_storage
from ml_core.utils import blur_faces_safety, pil_to_jpeg_bytes

logger = logging.getLogger(__name__)


RETICLE_W = 0.55
RETICLE_H = 0.70


def preprocess_capture(image_bytes: bytes) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = image.size

    crop_w = int(w * RETICLE_W)
    crop_h = int(h * RETICLE_H)
    x1 = max(0, (w - crop_w) // 2)
    y1 = max(0, (h - crop_h) // 2)
    image = image.crop((x1, y1, x1 + crop_w, y1 + crop_h))

    max_side = max(image.size)
    if max_side > 640:
        scale = 640 / max_side
        new_size = (int(image.size[0] * scale), int(image.size[1] * scale))
        image = image.resize(new_size)

    image = blur_faces_safety(image)
    return pil_to_jpeg_bytes(image, quality=80)


def create_capture(db: Session, user_id: str, image_bytes: bytes) -> Capture:
    capture_id = str(uuid.uuid4())
    processed = preprocess_capture(image_bytes)
    key = f"captures/{user_id}/{capture_id}.jpg"
    stored_path = get_storage().put_bytes(key, processed)

    capture = Capture(id=capture_id, user_id=user_id, image_path=stored_path, status="queued")
    db.add(capture)
    db.commit()
    db.refresh(capture)
    logger.info("capture_created", extra={"capture_id": capture.id})
    return capture
