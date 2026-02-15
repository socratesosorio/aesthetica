from __future__ import annotations

from PIL import Image

from ml_core.segment_and_detect import SegmentAndCatalogPipeline
from ml_core.shirt_catalog import CatalogProductMatch, ShirtCatalogResult, ShirtSignal


class _MockCatalogPipeline:
    def run(self, image_input, top_k: int = 5, use_rich_context: bool = False) -> ShirtCatalogResult:
        signal = ShirtSignal(
            is_shirt=True,
            confidence=0.92,
            garment_name="hoodie",
            brand_hint="Essentials",
            color_hint="black",
            style_tags=["streetwear"],
        )
        matches = [
            CatalogProductMatch(
                title="Fear of God Essentials Hoodie",
                product_url="https://example.com/essentials-hoodie",
                source="Example",
                price_text="$95",
                price_value=95.0,
                image_url=None,
                query="Essentials black hoodie",
                score=8.5,
            )
        ]
        return ShirtCatalogResult(status="ok", signal=signal, queries=["Essentials black hoodie"], matches=matches)


class _DualMockCatalogPipeline:
    def run(self, image_input, top_k: int = 5, use_rich_context: bool = False) -> ShirtCatalogResult:
        w, h = image_input.size
        # Full-frame result should win over crop result.
        if w >= 600:
            return ShirtCatalogResult(
                status="ok",
                signal=ShirtSignal(is_shirt=True, confidence=0.91, garment_name="hoodie", brand_hint="Essentials"),
                queries=["Essentials hoodie"],
                matches=[
                    CatalogProductMatch(
                        title="Fear of God Essentials Hoodie",
                        product_url="https://example.com/full",
                        source="Example",
                        price_text="$120",
                        price_value=120.0,
                        image_url=None,
                        query="Essentials hoodie",
                        score=9.0,
                    )
                ],
            )

        return ShirtCatalogResult(
            status="ok",
            signal=ShirtSignal(is_shirt=True, confidence=0.6, garment_name="shirt", brand_hint=None),
            queries=["gray shirt"],
            matches=[
                CatalogProductMatch(
                    title="Generic Shirt",
                    product_url="https://example.com/crop",
                    source="Example",
                    price_text="$20",
                    price_value=20.0,
                    image_url=None,
                    query="gray shirt",
                    score=1.0,
                )
            ],
        )


def test_segment_and_catalog_pipeline_returns_ranked_matches() -> None:
    pipeline = SegmentAndCatalogPipeline(catalog_pipeline=_MockCatalogPipeline())
    result = pipeline.run(Image.new("RGB", (640, 800), color=(20, 20, 20)), garment_type="top", top_k=3)

    assert result.segmentation.garment_type == "top"
    assert result.segmentation.crop_size[0] > 0
    assert result.segmentation.crop_size[1] > 0

    assert result.catalog.status == "ok"
    assert len(result.catalog.matches) == 1
    assert "essentials" in result.catalog.matches[0].title.lower()
    assert result.catalog.matches[0].price_value == 95.0


def test_segment_and_catalog_prefers_stronger_full_frame_result() -> None:
    pipeline = SegmentAndCatalogPipeline(catalog_pipeline=_DualMockCatalogPipeline())
    result = pipeline.run(Image.new("RGB", (640, 800), color=(20, 20, 20)), garment_type="top", top_k=3)
    assert result.catalog.signal.brand_hint == "Essentials"
    assert result.catalog.matches[0].product_url == "https://example.com/full"
