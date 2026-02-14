from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from .config import CONFIG
from .utils import ensure_dir

CATEGORIES = ["top", "bottom", "outerwear", "shoes", "accessories"]


@dataclass(slots=True)
class SearchResult:
    product_id: str
    similarity: float
    rank: int


class FaissCatalog:
    def __init__(self, faiss_dir: str | None = None) -> None:
        self.faiss_dir = Path(faiss_dir or CONFIG.faiss_dir)
        self._indexes: dict[str, faiss.Index] = {}
        self._mappings: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        ensure_dir(self.faiss_dir)
        for category in CATEGORIES:
            index_path = self.faiss_dir / f"{category}.index"
            map_path = self.faiss_dir / f"{category}_mapping.json"
            if not index_path.exists() or not map_path.exists():
                continue
            self._indexes[category] = faiss.read_index(str(index_path))
            self._mappings[category] = json.loads(map_path.read_text())

    def is_ready(self) -> bool:
        return bool(self._indexes)

    def query(self, category: str, vector: np.ndarray, top_k: int = 30) -> list[SearchResult]:
        if category not in self._indexes:
            return []
        idx = self._indexes[category]
        mapping = self._mappings[category]

        q = vector.astype(np.float32)[None, :]
        distances, ids = idx.search(q, top_k)
        out: list[SearchResult] = []
        for rank, (dist, fid) in enumerate(zip(distances[0], ids[0]), start=1):
            if int(fid) < 0:
                continue
            pid = mapping.get(str(int(fid)))
            if pid is None:
                continue
            out.append(SearchResult(product_id=pid, similarity=float(dist), rank=rank))
        return out

    def save_category(self, category: str, vectors: np.ndarray, id_map: dict[int, str]) -> None:
        ensure_dir(self.faiss_dir)
        vectors = vectors.astype(np.float32)
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        index_path = self.faiss_dir / f"{category}.index"
        map_path = self.faiss_dir / f"{category}_mapping.json"
        faiss.write_index(index, str(index_path))
        map_path.write_text(json.dumps({str(k): v for k, v in id_map.items()}, indent=2))


_global_catalog: FaissCatalog | None = None


def get_catalog() -> FaissCatalog:
    global _global_catalog
    if _global_catalog is None:
        _global_catalog = FaissCatalog()
        _global_catalog.load()
    return _global_catalog
