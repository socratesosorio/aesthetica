from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Product

logger = logging.getLogger(__name__)

_PRICE_CLEAN_RE = re.compile(r"[^0-9.,]")
_CATEGORY_QUERY_TERMS = {
    "top": "shirt blouse topwear",
    "bottom": "pants trousers skirt",
    "outerwear": "jacket coat outerwear",
    "shoes": "shoes sneakers boots",
    "accessories": "accessories bag hat jewelry belt",
}
_CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}


@dataclass(slots=True)
class WebProductCandidate:
    provider: str
    title: str
    brand: str
    category: str
    product_url: str
    image_url: str | None
    price: float | None
    currency: str | None
    similarity: float


class WebProductSearcher:
    def search(
        self,
        category: str,
        attributes: dict | None = None,
        image_url: str | None = None,
        limit: int = 5,
    ) -> list[WebProductCandidate]:
        raise NotImplementedError


class NoopWebProductSearcher(WebProductSearcher):
    def search(
        self,
        category: str,
        attributes: dict | None = None,
        image_url: str | None = None,
        limit: int = 5,
    ) -> list[WebProductCandidate]:
        return []


class SerpApiWebProductSearcher(WebProductSearcher):
    def __init__(self) -> None:
        self._warned_missing_key = False

    def search(
        self,
        category: str,
        attributes: dict | None = None,
        image_url: str | None = None,
        limit: int = 5,
    ) -> list[WebProductCandidate]:
        if not settings.web_search_enabled:
            return []

        if not settings.serpapi_api_key:
            if not self._warned_missing_key:
                logger.warning("web_search_key_missing_skip_search")
                self._warned_missing_key = True
            return []

        category = (category or "top").lower()
        target = max(1, min(limit, 10))

        candidates: list[WebProductCandidate] = []

        if settings.web_search_enable_lens and image_url and image_url.startswith(("http://", "https://")):
            try:
                candidates.extend(self._search_google_lens(category=category, image_url=image_url, limit=target * 2))
            except Exception:
                logger.exception("web_search_lens_failed")

        if len(candidates) < target:
            query = build_web_search_query(category=category, attributes=attributes or {})
            try:
                candidates.extend(self._search_google_shopping(category=category, query=query, limit=target * 3))
            except Exception:
                logger.exception("web_search_shopping_failed")

        return self._dedupe(candidates, limit=target)

    def _search_google_shopping(self, category: str, query: str, limit: int) -> list[WebProductCandidate]:
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": settings.serpapi_api_key,
            "gl": settings.web_search_country,
            "hl": settings.web_search_language,
            "num": max(5, min(limit, 20)),
        }
        payload = _serpapi_request(params)
        rows = payload.get("shopping_results") or payload.get("inline_shopping_results") or []

        out: list[WebProductCandidate] = []
        for idx, row in enumerate(rows, start=1):
            item = _candidate_from_result(
                row,
                provider="serpapi_google_shopping",
                category=category,
                rank=idx,
                fallback_similarity=1.0 - (idx - 1) * 0.03,
            )
            if item:
                out.append(item)
        return out

    def _search_google_lens(self, category: str, image_url: str, limit: int) -> list[WebProductCandidate]:
        params = {
            "engine": "google_lens",
            "url": image_url,
            "api_key": settings.serpapi_api_key,
            "gl": settings.web_search_country,
            "hl": settings.web_search_language,
        }
        payload = _serpapi_request(params)

        rows: list[dict[str, Any]] = []
        for key in ("visual_matches", "exact_matches", "products", "shopping_results"):
            values = payload.get(key)
            if isinstance(values, list):
                rows.extend([v for v in values if isinstance(v, dict)])

        out: list[WebProductCandidate] = []
        for idx, row in enumerate(rows[: max(5, min(limit, 30))], start=1):
            item = _candidate_from_result(
                row,
                provider="serpapi_google_lens",
                category=category,
                rank=idx,
                fallback_similarity=1.0 - (idx - 1) * 0.025,
            )
            if item:
                out.append(item)
        return out

    @staticmethod
    def _dedupe(items: list[WebProductCandidate], limit: int) -> list[WebProductCandidate]:
        seen: set[str] = set()
        out: list[WebProductCandidate] = []
        for item in items:
            key = item.product_url.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                break
        return out


def _serpapi_request(params: dict[str, Any]) -> dict[str, Any]:
    response = httpx.get(settings.serpapi_base_url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid SerpAPI response payload")
    if payload.get("error"):
        raise ValueError(f"SerpAPI error: {payload.get('error')}")
    return payload


def _candidate_from_result(
    row: dict[str, Any],
    provider: str,
    category: str,
    rank: int,
    fallback_similarity: float,
) -> WebProductCandidate | None:
    product_url = (
        row.get("product_link")
        or row.get("link")
        or row.get("serpapi_link")
        or row.get("shopping_result_link")
        or row.get("url")
    )
    title = row.get("title")
    if not product_url or not title:
        return None

    price, currency = _extract_price_currency(row)
    brand = row.get("source") or row.get("seller") or row.get("merchant_name") or "Web"
    image_url = row.get("thumbnail") or row.get("image") or row.get("image_url")

    sim = row.get("score")
    if isinstance(sim, (int, float)):
        similarity = float(sim)
    else:
        similarity = max(0.0, min(1.0, fallback_similarity))

    return WebProductCandidate(
        provider=provider,
        title=str(title).strip(),
        brand=str(brand).strip(),
        category=category,
        product_url=str(product_url).strip(),
        image_url=str(image_url).strip() if image_url else None,
        price=price,
        currency=currency,
        similarity=similarity,
    )


def _extract_price_currency(row: dict[str, Any]) -> tuple[float | None, str | None]:
    extracted = row.get("extracted_price")
    if isinstance(extracted, (int, float)):
        return float(extracted), _currency_from_price_string(str(row.get("price") or ""))

    price_text = str(row.get("price") or "").strip()
    if not price_text:
        return None, None

    cleaned = _PRICE_CLEAN_RE.sub("", price_text).replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        value = None
    return value, _currency_from_price_string(price_text)


def _currency_from_price_string(price: str) -> str | None:
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in price:
            return code
    return None


def _hex_to_color_name(hex_code: str) -> str:
    raw = (hex_code or "").strip().lstrip("#")
    if len(raw) != 6:
        return ""
    try:
        r = int(raw[0:2], 16)
        g = int(raw[2:4], 16)
        b = int(raw[4:6], 16)
    except ValueError:
        return ""

    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx < 40:
        return "black"
    if mn > 220:
        return "white"
    if abs(r - g) < 10 and abs(g - b) < 10:
        return "gray"

    if r >= g and r >= b:
        return "red" if g < 130 else "orange"
    if g >= r and g >= b:
        return "green"
    return "blue"


def build_web_search_query(category: str, attributes: dict) -> str:
    terms: list[str] = []

    for c in attributes.get("colors", [])[:2]:
        hex_code = c.get("hex")
        if isinstance(hex_code, str):
            name = _hex_to_color_name(hex_code)
            if name:
                terms.append(name)

    silhouette = attributes.get("silhouette")
    if isinstance(silhouette, str) and silhouette in {"slim", "regular", "oversized"}:
        terms.append(silhouette)

    pattern = attributes.get("pattern", {})
    if isinstance(pattern, dict):
        pattern_type = pattern.get("type")
        if isinstance(pattern_type, str):
            terms.append(pattern_type)

    descriptor = _CATEGORY_QUERY_TERMS.get(category, category)
    terms.append(descriptor)
    terms.append("fashion")
    return " ".join(t for t in terms if t).strip()


def web_product_id(provider: str, product_url: str) -> str:
    digest = hashlib.sha1(f"{provider}|{product_url}".encode("utf-8")).hexdigest()[:24]
    return f"web_{digest}"


def upsert_web_product(db: Session, candidate: WebProductCandidate) -> Product:
    pid = web_product_id(candidate.provider, candidate.product_url)
    product = db.query(Product).filter(Product.id == pid).first()
    if product is None:
        product = Product(
            id=pid,
            title=candidate.title,
            brand=candidate.brand,
            category=candidate.category,
            price=candidate.price,
            currency=candidate.currency,
            image_url=candidate.image_url,
            product_url=candidate.product_url,
            color_tags={"source": candidate.provider},
        )
        db.add(product)
        db.flush()
        return product

    product.title = candidate.title or product.title
    product.brand = candidate.brand or product.brand
    product.category = candidate.category or product.category
    product.price = candidate.price if candidate.price is not None else product.price
    product.currency = candidate.currency or product.currency
    product.image_url = candidate.image_url or product.image_url
    product.product_url = candidate.product_url or product.product_url
    tags = product.color_tags or {}
    tags["source"] = candidate.provider
    product.color_tags = tags
    db.flush()
    return product


_searcher: WebProductSearcher | None = None


def get_web_product_searcher() -> WebProductSearcher:
    global _searcher
    if _searcher is not None:
        return _searcher

    provider = settings.web_search_provider.lower().strip()
    if provider == "serpapi":
        _searcher = SerpApiWebProductSearcher()
    else:
        _searcher = NoopWebProductSearcher()
    return _searcher
