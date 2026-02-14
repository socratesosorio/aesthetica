from __future__ import annotations

from app.services.web_product_search import build_web_search_query, web_product_id


def test_build_web_search_query_uses_attributes():
    query = build_web_search_query(
        "top",
        {
            "colors": [{"hex": "#101010", "pct": 0.6}, {"hex": "#F4F4F4", "pct": 0.4}],
            "silhouette": "oversized",
            "pattern": {"type": "solid", "confidence": 0.9},
        },
    )
    assert "black" in query
    assert "white" in query
    assert "oversized" in query
    assert "solid" in query
    assert "topwear" in query


def test_web_product_id_is_deterministic():
    a = web_product_id("serpapi_google_shopping", "https://shop.example/item/123")
    b = web_product_id("serpapi_google_shopping", "https://shop.example/item/123")
    c = web_product_id("serpapi_google_lens", "https://shop.example/item/123")
    assert a == b
    assert a != c
    assert a.startswith("web_")
