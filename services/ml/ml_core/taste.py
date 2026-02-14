from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import CONFIG
from .embeddings import get_embedder
from .utils import l2_normalize

AXES = {
    "minimal_maximal": (
        "minimalist outfit, clean lines, muted palette",
        "maximalist outfit, bold patterns, layered accessories",
    ),
    "structured_relaxed": (
        "structured tailoring, sharp silhouette",
        "relaxed fit, draped fabrics, casual silhouette",
    ),
    "neutral_color_forward": (
        "neutral tones outfit, beige, black, white",
        "bright colorful outfit, saturated colors",
    ),
    "classic_experimental": (
        "classic timeless outfit, traditional staples",
        "avant-garde experimental outfit, unusual silhouettes",
    ),
    "casual_formal": ("casual everyday outfit", "formal outfit, eveningwear, business formal"),
}


@dataclass(slots=True)
class TasteProfileEngine:
    scale: float = CONFIG.radar_scale
    bias: float = CONFIG.radar_bias
    alpha: float = CONFIG.radar_alpha

    def update_embedding(self, previous: np.ndarray | None, capture_embedding: np.ndarray) -> np.ndarray:
        capture_embedding = l2_normalize(capture_embedding.astype(np.float32))
        if previous is None:
            return capture_embedding
        updated = self.alpha * previous.astype(np.float32) + (1.0 - self.alpha) * capture_embedding
        return l2_normalize(updated)

    def _axis_vector(self, axis_name: str) -> np.ndarray:
        a, b = AXES[axis_name]
        vec = get_embedder().text_embedding(b) - get_embedder().text_embedding(a)
        return l2_normalize(vec.astype(np.float32))

    def radar_scores(self, user_embedding: np.ndarray) -> dict[str, float]:
        ue = l2_normalize(user_embedding.astype(np.float32))
        scores: dict[str, float] = {}
        for axis_name in AXES:
            axis_vec = self._axis_vector(axis_name)
            raw = float(np.dot(ue, axis_vec))
            mapped = max(0.0, min(100.0, raw * self.scale + self.bias))
            scores[axis_name] = round(mapped, 2)
        return scores

    def delta(self, old: dict[str, float] | None, new: dict[str, float]) -> dict[str, float]:
        if old is None:
            return {k: round(v, 2) for k, v in new.items()}
        return {k: round(new[k] - old.get(k, 0.0), 2) for k in new}


def generate_aesthetic_summary(attributes: dict, radar: dict[str, float]) -> str:
    colors = attributes.get("colors", [])
    top_color = colors[0]["hex"] if colors else "mixed tones"
    silhouette = attributes.get("silhouette", "regular")

    structure = "structured" if radar.get("structured_relaxed", 50) < 45 else "relaxed"
    minimal = "minimalist" if radar.get("minimal_maximal", 50) < 45 else "expressive"
    formality = "formal" if radar.get("casual_formal", 50) > 55 else "casual"

    return f"{structure.capitalize()} {top_color.lower()} {silhouette} styling with {minimal} {formality} energy."
