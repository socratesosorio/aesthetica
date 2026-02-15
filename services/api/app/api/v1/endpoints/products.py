from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Capture, Garment, Product, User, UserProfile
from app.schemas.product import ProductRecommendationOut, ProductSearchOut
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
                    image_url=p.image_url,
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
                    image_url=candidate.image_url,
                    source=candidate.provider,
                    product_url=candidate.product_url,
                    similarity=candidate.similarity,
                    rank=rank,
                )
            )
            rank += 1

    return out[: max(1, min(top_k, 100))]


@router.get("/products/recommendations", response_model=list[ProductRecommendationOut])
def recommended_products(
    limit: int = Query(default=24, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProductRecommendationOut]:
    """
    Personalized product feed.

    Strategy:
    - If the user has an embedding_vector: query FAISS per category using that vector.
    - Otherwise: fall back to a simple "trending" list from the local catalog.
    """
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    embedding: np.ndarray | None = None
    if profile is not None and profile.embedding_vector:
        embedding = np.frombuffer(profile.embedding_vector, dtype=np.float32)

    # Choose categories based on user's category bias (if present), else default.
    default_categories = ["top", "bottom", "outerwear", "shoes", "accessories"]
    categories = default_categories
    if profile is not None and profile.category_bias:
        ranked = sorted(profile.category_bias.items(), key=lambda kv: float(kv[1] or 0.0), reverse=True)
        cats = [k for k, _ in ranked if isinstance(k, str)]
        cats = [c for c in cats if c in default_categories]
        if cats:
            categories = cats[: min(5, len(cats))]

    # Trending fallback: pick from DB
    if embedding is None:
        rows = db.query(Product).limit(limit).all()
        return [
            ProductRecommendationOut(
                product_id=p.id,
                title=p.title,
                brand=p.brand,
                category=p.category,
                price=p.price,
                currency=p.currency,
                image_url=p.image_url,
                product_url=p.product_url,
                reason="Trending now",
                score=None,
            )
            for p in rows
        ]

    per_cat = max(3, math.ceil(limit / max(1, len(categories))))
    seen: set[str] = set()
    out: list[ProductRecommendationOut] = []

    for cat in categories:
        ranked = get_catalog().query(cat, embedding, top_k=min(30, max(3, per_cat * 3)))
        pids = [r.product_id for r in ranked]
        products = {p.id: p for p in db.query(Product).filter(Product.id.in_(pids)).all()}
        # Keep order by rank
        for r in ranked:
            p = products.get(r.product_id)
            if p is None or p.id in seen:
                continue
            seen.add(p.id)
            out.append(
                ProductRecommendationOut(
                    product_id=p.id,
                    title=p.title,
                    brand=p.brand,
                    category=p.category,
                    price=p.price,
                    currency=p.currency,
                    image_url=p.image_url,
                    product_url=p.product_url,
                    reason=f"Recommended for your taste · {cat}",
                    score=r.similarity,
                )
            )
            if len(out) >= limit:
                return out

    # If we didn't fill, pad with trending.
    if len(out) < limit:
        rows = db.query(Product).limit(limit * 2).all()
        for p in rows:
            if p.id in seen:
                continue
            seen.add(p.id)
            out.append(
                ProductRecommendationOut(
                    product_id=p.id,
                    title=p.title,
                    brand=p.brand,
                    category=p.category,
                    price=p.price,
                    currency=p.currency,
                    image_url=p.image_url,
                    product_url=p.product_url,
                    reason="Trending now",
                    score=None,
                )
            )
            if len(out) >= limit:
                break

    return out
