from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Capture, Garment, Product, User
from app.schemas.product import ProductSearchOut
from ml_core.config import CONFIG
from ml_core.retrieval import get_catalog
from ml_core.utils import b64_to_ndarray

router = APIRouter()


@router.get("/products/search", response_model=list[ProductSearchOut])
def search_products(
    embedding_b64: str | None = Query(default=None),
    capture_id: str | None = Query(default=None),
    garment_type: str | None = Query(default="top"),
    top_k: int = Query(default=30),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProductSearchOut]:
    vector: np.ndarray | None = None
    category = (garment_type or "top").lower()

    if embedding_b64:
        vector = b64_to_ndarray(embedding_b64, CONFIG.embedding_dim)
    elif capture_id:
        capture = db.query(Capture).filter(Capture.id == capture_id, Capture.user_id == user.id).first()
        if capture is None:
            raise HTTPException(status_code=404, detail="Capture not found")

        garment = (
            db.query(Garment)
            .filter(Garment.capture_id == capture_id, Garment.garment_type == category)
            .order_by(Garment.id.asc())
            .first()
        )
        if garment is not None and garment.embedding_vector:
            vector = np.frombuffer(garment.embedding_vector, dtype=np.float32)
        elif capture.global_embedding:
            vector = np.frombuffer(capture.global_embedding, dtype=np.float32)
            category = "top"

    if vector is None:
        raise HTTPException(status_code=400, detail="Provide embedding_b64 or capture_id")

    ranked = get_catalog().query(category, vector, top_k=max(1, min(top_k, 100)))
    if not ranked:
        return []

    pids = [r.product_id for r in ranked]
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(pids)).all()}

    out: list[ProductSearchOut] = []
    for r in ranked:
        p = products.get(r.product_id)
        if p is None:
            continue
        out.append(
            ProductSearchOut(
                product_id=p.id,
                title=p.title,
                brand=p.brand,
                category=p.category,
                price=p.price,
                currency=p.currency,
                product_url=p.product_url,
                similarity=r.similarity,
                rank=r.rank,
            )
        )
    return out
