from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Capture, Garment, Product, User
from app.schemas.product import ProductSearchOut
from app.services.web_product_search import get_web_product_searcher, web_product_id
from ml_core.config import CONFIG
from ml_core.retrieval import get_catalog
from ml_core.utils import b64_to_ndarray

router = APIRouter()


def _as_public_http_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return None


@router.get("/products/search", response_model=list[ProductSearchOut])
def search_products(
    embedding_b64: str | None = Query(default=None),
    capture_id: str | None = Query(default=None),
    garment_type: str | None = Query(default="top"),
    include_web: bool = Query(default=False),
    top_k: int = Query(default=30),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProductSearchOut]:
    vector: np.ndarray | None = None
    category = (garment_type or "top").lower()
    attrs: dict = {}
    image_url: str | None = None

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
            attrs = garment.attributes_json or {}
            image_url = garment.crop_path
        elif capture.global_embedding:
            vector = np.frombuffer(capture.global_embedding, dtype=np.float32)
            category = "top"
            attrs = capture.global_attributes_json or {}
            image_url = capture.image_path

    if vector is None and not include_web:
        raise HTTPException(status_code=400, detail="Provide embedding_b64 or capture_id")

    out: list[ProductSearchOut] = []
    seen_ids: set[str] = set()

    if vector is not None:
        ranked = get_catalog().query(category, vector, top_k=max(1, min(top_k, 100)))
        pids = [r.product_id for r in ranked]
        products = {p.id: p for p in db.query(Product).filter(Product.id.in_(pids)).all()}

        for r in ranked:
            p = products.get(r.product_id)
            if p is None:
                continue
            seen_ids.add(p.id)
            out.append(
                ProductSearchOut(
                    product_id=p.id,
                    title=p.title,
                    brand=p.brand,
                    category=p.category,
                    price=p.price,
                    currency=p.currency,
                    source="catalog",
                    product_url=p.product_url,
                    similarity=r.similarity,
                    rank=r.rank,
                )
            )

    if include_web:
        web_limit = max(1, min(top_k, 10))
        web_candidates = get_web_product_searcher().search(
            category=category,
            attributes=attrs,
            image_url=_as_public_http_url(image_url),
            limit=web_limit,
        )
        rank = (out[-1].rank if out else 0) + 1
        for candidate in web_candidates:
            pid = web_product_id(candidate.provider, candidate.product_url)
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            out.append(
                ProductSearchOut(
                    product_id=pid,
                    title=candidate.title,
                    brand=candidate.brand,
                    category=candidate.category,
                    price=candidate.price,
                    currency=candidate.currency,
                    source=candidate.provider,
                    product_url=candidate.product_url,
                    similarity=candidate.similarity,
                    rank=rank,
                )
            )
            rank += 1

    return out[: max(1, min(top_k, 100))]
