"""Segmentation + catalog retrieval pipeline for Aesthetica.

Current active flow:
  image -> heuristic garment crop -> OpenAI+Serp catalog retrieval

This module intentionally excludes legacy Google Vision web-detection logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

from PIL import Image

from .shirt_catalog import ShirtCatalogPipeline, ShirtCatalogResult


GARMENT_REGIONS: dict[str, tuple[float, float, float, float]] = {
    "top": (0.15, 0.55, 0.15, 0.85),
    "bottom": (0.50, 0.88, 0.20, 0.80),
    "outerwear": (0.10, 0.60, 0.10, 0.90),
    "shoes": (0.85, 1.00, 0.20, 0.80),
    "accessories": (0.00, 0.18, 0.25, 0.75),
}


@dataclass(slots=True)
class SegmentationInfo:
    garment_type: str
    method: str = "heuristic"
    region_pct: tuple[float, float, float, float] = (0, 0, 0, 0)
    crop_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    original_size: tuple[int, int] = (0, 0)
    crop_size: tuple[int, int] = (0, 0)


@dataclass(slots=True)
class SegmentAndCatalogResult:
    garment_crop: Image.Image
    segmentation: SegmentationInfo
    catalog: ShirtCatalogResult


def _load_image(image_input: Union[str, Path, Image.Image]) -> Image.Image:
    if isinstance(image_input, (str, Path)):
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        return Image.open(path).convert("RGB")
    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")
    raise TypeError(f"Expected str, Path, or PIL Image, got {type(image_input).__name__}")


def segment_garment(
    image_input: Union[str, Path, Image.Image],
    garment_type: str = "top",
) -> tuple[Image.Image, SegmentationInfo]:
    if garment_type not in GARMENT_REGIONS:
        raise ValueError(
            f"Unknown garment_type={garment_type!r}. "
            f"Choose from: {list(GARMENT_REGIONS.keys())}"
        )

    image = _load_image(image_input)
    w, h = image.size
    y1_pct, y2_pct, x1_pct, x2_pct = GARMENT_REGIONS[garment_type]

    x1 = max(0, int(w * x1_pct))
    x2 = min(w, int(w * x2_pct))
    y1 = max(0, int(h * y1_pct))
    y2 = min(h, int(h * y2_pct))

    crop = image.crop((x1, y1, x2, y2))

    info = SegmentationInfo(
        garment_type=garment_type,
        method="heuristic",
        region_pct=(y1_pct, y2_pct, x1_pct, x2_pct),
        crop_bbox=(x1, y1, x2, y2),
        original_size=(w, h),
        crop_size=crop.size,
    )
    return crop, info


class SegmentAndCatalogPipeline:
    def __init__(self, catalog_pipeline: ShirtCatalogPipeline | None = None) -> None:
        self.catalog_pipeline = catalog_pipeline or ShirtCatalogPipeline()

    def run(
        self,
        image_input: Union[str, Path, Image.Image],
        garment_type: str = "top",
        top_k: int = 5,
        use_rich_context: bool = False,
    ) -> SegmentAndCatalogResult:
        original = _load_image(image_input)
        crop, seg_info = segment_garment(original, garment_type=garment_type)
        # Fast path: single catalog call on full image.
        catalog = self.catalog_pipeline.run(original, top_k=top_k, use_rich_context=use_rich_context)

        return SegmentAndCatalogResult(
            garment_crop=crop,
            segmentation=seg_info,
            catalog=catalog,
        )
