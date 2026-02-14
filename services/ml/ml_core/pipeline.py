from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .attributes import AttributeExtractor
from .embeddings import get_embedder
from .retrieval import CATEGORIES, FaissCatalog
from .segmentation import SegmentationProvider
from .taste import TasteProfileEngine
from .utils import l2_normalize


@dataclass(slots=True)
class GarmentInference:
    garment_type: str
    embedding: np.ndarray
    attributes: dict
    crop: Image.Image


@dataclass(slots=True)
class CaptureInference:
    global_embedding: np.ndarray
    garments: list[GarmentInference]
    global_attributes: dict


class CapturePipeline:
    def __init__(self, catalog: FaissCatalog) -> None:
        self.catalog = catalog
        self.segmenter = SegmentationProvider()
        self.attr = AttributeExtractor()
        self.taste = TasteProfileEngine()

    def run(self, image: Image.Image) -> CaptureInference:
        segmentation = self.segmenter.parse(image)
        global_embedding = get_embedder().image_embedding(image)
        global_attributes = self.attr.extract(image)

        garments: list[GarmentInference] = []
        for category in CATEGORIES:
            crop = segmentation.crops.get(category)
            if crop is None:
                continue
            rgb = crop.convert("RGB")
            if rgb.size[0] * rgb.size[1] <= 10:
                continue
            emb = get_embedder().image_embedding(rgb)
            attrs = self.attr.extract(rgb)
            garments.append(
                GarmentInference(garment_type=category, embedding=l2_normalize(emb), attributes=attrs, crop=crop)
            )

        return CaptureInference(
            global_embedding=l2_normalize(global_embedding),
            garments=garments,
            global_attributes=global_attributes,
        )
