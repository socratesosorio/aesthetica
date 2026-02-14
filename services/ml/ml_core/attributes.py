from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .embeddings import get_embedder
from .utils import color_entropy, dominant_colors, edge_density


@dataclass(slots=True)
class AttributeExtractor:
    def extract(self, image: Image.Image) -> dict:
        colors = dominant_colors(image, k=4)
        color_payload = [{"hex": c, "pct": round(p, 4)} for c, p in colors]

        ed = edge_density(image)
        ent = color_entropy(image)
        patterned_score = min(1.0, (ed * 2.2 + ent / 10.0))
        pattern_type = "patterned" if patterned_score >= 0.45 else "solid"

        emb = get_embedder().image_embedding(image)

        def bipolar_score(pos: str, neg: str) -> float:
            e_pos = get_embedder().text_embedding(pos)
            e_neg = get_embedder().text_embedding(neg)
            raw = float(np.dot(emb, e_pos) - np.dot(emb, e_neg))
            mapped = max(0.0, min(100.0, raw * 50.0 + 50.0))
            return round(mapped, 2)

        formality = bipolar_score("formal outfit, eveningwear, business formal", "casual everyday outfit")
        minimalism = bipolar_score(
            "minimalist outfit, clean lines, muted palette",
            "maximalist outfit, bold patterns, layered accessories",
        )
        structure = bipolar_score(
            "structured tailoring, sharp silhouette", "relaxed fit, draped fabrics, casual silhouette"
        )

        silhouette_labels = {
            "slim": "slim fitted silhouette",
            "regular": "regular balanced silhouette",
            "oversized": "oversized loose silhouette",
        }
        sims = {
            k: float(np.dot(emb, get_embedder().text_embedding(v))) for k, v in silhouette_labels.items()
        }
        silhouette = max(sims.items(), key=lambda kv: kv[1])[0] if sims else "unknown"

        notes = []
        if formality > 65:
            notes.append("elevated polish")
        if minimalism > 65:
            notes.append("clean minimal direction")
        if pattern_type == "patterned":
            notes.append("visual texture present")

        return {
            "colors": color_payload,
            "pattern": {"type": pattern_type, "confidence": round(patterned_score, 3)},
            "formality": formality,
            "structure": structure,
            "minimalism": minimalism,
            "silhouette": silhouette,
            "notes": notes,
        }
