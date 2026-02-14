from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
from PIL import Image

from .embeddings import get_embedder
from .utils import masked_crop_rgba

GARMENT_BUCKETS = ["top", "bottom", "outerwear", "shoes", "accessories"]


@dataclass(slots=True)
class SegmentationResult:
    masks: dict[str, np.ndarray]
    crops: dict[str, Image.Image]


class SegmentationProvider:
    """Pluggable human parser. Uses FASHN parser if available, fallback heuristic otherwise."""

    def __init__(self) -> None:
        self._backend = None
        self._load_backend()

    def _load_backend(self) -> None:
        try:
            # optional dependency, API may vary by version
            from fashn_human_parser import HumanParser  # type: ignore

            self._backend = HumanParser()
        except Exception:
            self._backend = None

    def _parse_map(self, image: Image.Image) -> np.ndarray | None:
        if self._backend is None:
            return None
        try:
            out = self._backend(image)
            if isinstance(out, dict) and "segmentation" in out:
                return np.array(out["segmentation"], dtype=np.int32)
            return np.array(out, dtype=np.int32)
        except Exception:
            return None

    def _heuristic_masks(self, image: Image.Image) -> dict[str, np.ndarray]:
        h, w = image.size[1], image.size[0]
        masks = {k: np.zeros((h, w), dtype=np.uint8) for k in GARMENT_BUCKETS}

        # Body-centric heuristic regions when parser model is unavailable.
        masks["top"][int(h * 0.15) : int(h * 0.55), int(w * 0.15) : int(w * 0.85)] = 1
        masks["bottom"][int(h * 0.50) : int(h * 0.90), int(w * 0.20) : int(w * 0.80)] = 1
        masks["shoes"][int(h * 0.86) : h, int(w * 0.22) : int(w * 0.78)] = 1
        masks["accessories"][int(h * 0.03) : int(h * 0.25), int(w * 0.10) : int(w * 0.90)] = 1

        # Infer outerwear by CLIP text affinity on upper body region.
        upper = image.crop((int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.6)))
        emb = get_embedder().image_embedding(upper)
        jacket = get_embedder().text_embedding("jacket coat outerwear")
        shirt = get_embedder().text_embedding("shirt tee top")
        if float(np.dot(emb, jacket)) > float(np.dot(emb, shirt)):
            masks["outerwear"][int(h * 0.10) : int(h * 0.60), int(w * 0.10) : int(w * 0.90)] = 1

        return masks

    def _map_parser_classes(self, seg: np.ndarray, image: Image.Image) -> dict[str, np.ndarray]:
        # FASHN labels vary by model version. This mapping uses broad class-id bands.
        h, w = seg.shape
        masks = {k: np.zeros((h, w), dtype=np.uint8) for k in GARMENT_BUCKETS}

        # Approximate mappings (model-dependent):
        top_ids = {4, 5, 6, 7, 8, 9, 10}
        bottom_ids = {12, 13, 14, 15}
        accessory_ids = {16, 17, 18, 19, 20, 21, 22}
        feet_ids = {23, 24, 25}
        outerwear_ids = {11}

        for cid in top_ids:
            masks["top"] |= (seg == cid).astype(np.uint8)
        for cid in bottom_ids:
            masks["bottom"] |= (seg == cid).astype(np.uint8)
        for cid in accessory_ids:
            masks["accessories"] |= (seg == cid).astype(np.uint8)
        for cid in outerwear_ids:
            masks["outerwear"] |= (seg == cid).astype(np.uint8)

        feet_mask = np.zeros_like(seg, dtype=np.uint8)
        for cid in feet_ids:
            feet_mask |= (seg == cid).astype(np.uint8)

        # Shoe inference from feet + bottom-of-frame constraint.
        h0 = int(seg.shape[0] * 0.75)
        masks["shoes"][h0:, :] = feet_mask[h0:, :]

        # If no outerwear, infer via CLIP on top region.
        if masks["outerwear"].sum() == 0:
            pil_top = masked_crop_rgba(image, masks["top"]).convert("RGB")
            emb = get_embedder().image_embedding(pil_top)
            jacket = get_embedder().text_embedding("jacket coat outerwear")
            shirt = get_embedder().text_embedding("shirt top")
            if float(np.dot(emb, jacket)) > float(np.dot(emb, shirt)):
                masks["outerwear"] = masks["top"].copy()

        return masks

    def parse(self, image: Image.Image) -> SegmentationResult:
        seg = self._parse_map(image)
        masks = self._map_parser_classes(seg, image) if seg is not None else self._heuristic_masks(image)
        crops: Dict[str, Image.Image] = {}

        for bucket, mask in masks.items():
            crops[bucket] = masked_crop_rgba(image, mask)

        return SegmentationResult(masks=masks, crops=crops)
