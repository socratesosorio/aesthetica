from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests
from PIL import Image

from ml_core.shirt_catalog import (
    CatalogProductMatch,
    OpenAIShirtAnalyzer,
    SerpApiShoppingSearch,
    ShirtCatalogPipeline,
    ShirtSignal,
)


class _MockAnalyzer:
    def __init__(self, signal: ShirtSignal) -> None:
        self._signal = signal

    def analyze(self, image):
        return self._signal


class _MockSearch:
    def __init__(self, rows: dict[str, list[CatalogProductMatch]]) -> None:
        self._rows = rows

    def search(self, query: str, max_results: int = 10) -> list[CatalogProductMatch]:
        return list(self._rows.get(query, []))


@pytest.fixture()
def sample_signal() -> ShirtSignal:
    return ShirtSignal(
        is_shirt=True,
        confidence=0.93,
        garment_name="hoodie",
        brand_hint="Essentials",
        color_hint="black",
        style_tags=["streetwear"],
    )


def _mk(title: str, link: str, query: str, price: float | None = None) -> CatalogProductMatch:
    return CatalogProductMatch(
        title=title,
        product_url=link,
        source="Test",
        price_text=f"${price}" if price is not None else None,
        price_value=price,
        image_url=None,
        query=query,
        score=0.0,
    )


def test_shirt_catalog_ranks_brand_precisely(sample_signal: ShirtSignal) -> None:
    queries = [
        "Essentials black hoodie streetwear",
        "Essentials hoodie",
        "black hoodie streetwear",
    ]
    rows = {
        queries[0]: [
            _mk("Fear of God Essentials Black Pullover Hoodie", "https://store/a", queries[0], 95.0),
            _mk("Generic Black Hoodie", "https://store/b", queries[0], 30.0),
        ],
        queries[1]: [
            _mk("Essentials Hoodie Stretch Logo", "https://store/c", queries[1], 99.0),
        ],
        queries[2]: [
            _mk("Streetwear Black Fleece Hoodie", "https://store/d", queries[2], 45.0),
        ],
    }

    pipeline = ShirtCatalogPipeline(analyzer=_MockAnalyzer(sample_signal), search=_MockSearch(rows), min_confidence=0.7)
    result = pipeline.run(Image.new("RGB", (320, 320), color=(30, 30, 30)), top_k=3)

    assert result.status == "ok"
    # Fast pipeline may use a single primary shopping query.
    assert len(result.matches) >= 2
    assert "essentials" in result.matches[0].title.lower()
    assert result.matches[0].score > result.matches[-1].score


def test_shirt_catalog_rejects_low_confidence() -> None:
    signal = ShirtSignal(is_shirt=True, confidence=0.51, garment_name="shirt")
    pipeline = ShirtCatalogPipeline(analyzer=_MockAnalyzer(signal), search=_MockSearch({}), min_confidence=0.75)

    result = pipeline.run(Image.new("RGB", (200, 200), color=(10, 10, 10)))

    assert result.status == "no_precise_shirt_detected"
    assert result.matches == []
    assert result.queries == []


def test_shirt_catalog_without_brand_hint_stays_generic() -> None:
    signal = ShirtSignal(is_shirt=True, confidence=0.72, garment_name="shirt", brand_hint=None, color_hint="gray")
    rows = {
        "gray hoodie": [],
        "gray shirt": [
            _mk("Generic Gray Tee", "https://store/f", "gray shirt", 20.0),
        ],
    }
    pipeline = ShirtCatalogPipeline(analyzer=_MockAnalyzer(signal), search=_MockSearch(rows), min_confidence=0.7)
    result = pipeline.run(Image.new("RGB", (200, 200), color=(100, 100, 100)))

    assert result.status == "ok"
    assert result.signal.brand_hint is None
    assert "generic" in result.matches[0].title.lower()


@pytest.mark.live_api
def test_live_shirt_catalog_pipeline() -> None:
    if os.getenv("RUN_LIVE_SHIRT_CATALOG_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_SHIRT_CATALOG_TESTS=1 to run live tests")
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("SERPAPI_API_KEY"):
        pytest.skip("OPENAI_API_KEY and SERPAPI_API_KEY are required")

    image_path = Path("tests/web_detection/test_images/nike.jpg")
    if not image_path.exists():
        pytest.skip("Missing live test image. Download tests/web_detection images first")

    pipeline = ShirtCatalogPipeline(
        analyzer=OpenAIShirtAnalyzer.from_env(),
        search=SerpApiShoppingSearch.from_env(),
        min_confidence=0.7,
    )

    try:
        result = pipeline.run(image_path, top_k=3)
    except requests.RequestException as exc:
        pytest.skip(f"Live API call unavailable in this environment: {exc}")

    assert result.signal.confidence >= 0.0
    assert result.status in {"ok", "no_products_found", "no_precise_shirt_detected"}
    if result.status == "ok":
        assert len(result.matches) >= 1
        assert result.matches[0].product_url.startswith("http")
