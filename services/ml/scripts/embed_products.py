#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from ml_core.config import CONFIG
from ml_core.embeddings import get_embedder
from ml_core.retrieval import CATEGORIES, FaissCatalog
from ml_core.utils import load_image_from_path_or_url


def read_products(csv_path: str) -> list[dict]:
    with Path(csv_path).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def main() -> None:
    load_dotenv()
    products = read_products(CONFIG.product_csv_path)
    grouped: dict[str, list[dict]] = defaultdict(list)

    for p in products:
        cat = p.get("category", "").strip().lower()
        if cat in CATEGORIES:
            grouped[cat].append(p)

    catalog = FaissCatalog(CONFIG.faiss_dir)

    for category, rows in grouped.items():
        vectors = []
        id_map: dict[int, str] = {}
        for i, row in enumerate(rows):
            img_ref = row.get("image_url") or row.get("local_image_path") or ""
            image = load_image_from_path_or_url(img_ref)
            vec = get_embedder().image_embedding(image)
            vectors.append(vec)
            id_map[i] = row["product_id"]

        if not vectors:
            continue
        arr = np.stack(vectors).astype(np.float32)
        catalog.save_category(category, arr, id_map)
        print(f"indexed {len(vectors)} products for {category}")


if __name__ == "__main__":
    main()
