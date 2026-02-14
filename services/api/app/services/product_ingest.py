from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from app.models import Product
from ml_core.embeddings import get_embedder
from ml_core.retrieval import CATEGORIES, FaissCatalog
from ml_core.utils import load_image_from_path_or_url


def ingest_products_csv(db: Session, csv_path: str) -> int:
    path = Path(csv_path)
    if not path.exists():
        return 0

    inserted = 0
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row["product_id"]
            existing = db.query(Product).filter(Product.id == pid).first()
            if existing:
                existing.title = row.get("title", existing.title)
                existing.brand = row.get("brand", existing.brand)
                existing.category = row.get("category", existing.category)
                existing.price = float(row["price"]) if row.get("price") else None
                existing.currency = row.get("currency")
                existing.image_url = row.get("image_url") or row.get("local_image_path")
                existing.product_url = row.get("product_url", existing.product_url)
                inserted += 1
                continue

            db.add(
                Product(
                    id=pid,
                    title=row["title"],
                    brand=row.get("brand", "Unknown"),
                    category=row.get("category", "top"),
                    price=float(row["price"]) if row.get("price") else None,
                    currency=row.get("currency") or "USD",
                    image_url=row.get("image_url") or row.get("local_image_path"),
                    product_url=row.get("product_url", "https://example.com"),
                    color_tags=None,
                )
            )
            inserted += 1

    db.commit()
    return inserted


def rebuild_faiss_from_db(db: Session, faiss_dir: str) -> dict[str, int]:
    catalog = FaissCatalog(faiss_dir)
    stats: dict[str, int] = {}

    for category in CATEGORIES:
        rows = db.query(Product).filter(Product.category == category).all()
        if not rows:
            continue

        vectors = []
        id_map: dict[int, str] = {}
        for i, row in enumerate(rows):
            image = load_image_from_path_or_url(row.image_url or row.product_url)
            vec = get_embedder().image_embedding(image)
            vectors.append(vec)
            id_map[i] = row.id

        arr = np.stack(vectors).astype(np.float32)
        catalog.save_category(category, arr, id_map)
        stats[category] = len(rows)

    return stats
