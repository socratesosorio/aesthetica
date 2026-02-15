from __future__ import annotations

import base64
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import requests
from PIL import Image


class OpenAIQuotaExceededError(RuntimeError):
    """Raised when OpenAI returns quota/rate-limit exhaustion."""


@dataclass(slots=True)
class ShirtSignal:
    is_shirt: bool
    confidence: float
    garment_name: str
    brand_hint: str | None = None
    color_hint: str | None = None
    style_tags: list[str] = field(default_factory=list)
    exact_item_hint: str | None = None
    context_terms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CatalogProductMatch:
    title: str
    product_url: str
    source: str | None
    price_text: str | None
    price_value: float | None
    image_url: str | None
    query: str
    score: float


@dataclass(slots=True)
class ShirtCatalogResult:
    status: str
    signal: ShirtSignal
    queries: list[str]
    matches: list[CatalogProductMatch]


class ShirtAnalyzer(Protocol):
    def analyze(self, image: Image.Image) -> ShirtSignal:
        ...


class ShoppingSearch(Protocol):
    def search(self, query: str, max_results: int = 10) -> list[CatalogProductMatch]:
        ...


class OpenAIShirtAnalyzer:
    _last_call_ts: float = 0.0

    def __init__(self, api_key: str, model: str | None = None, timeout_sec: int = 25) -> None:
        self.api_key = api_key
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
        self.timeout_sec = timeout_sec
        self.min_interval_sec = float(os.getenv("OPENAI_MIN_INTERVAL_SEC", "2.5"))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "5"))

    @classmethod
    def from_env(cls) -> "OpenAIShirtAnalyzer":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIShirtAnalyzer")
        return cls(api_key=api_key)

    def analyze(self, image: Image.Image) -> ShirtSignal:
        payload_images = _candidate_data_urls(image)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Single consolidated extraction call (fast mode).
        system_prompt = (
            "You are a fashion product extractor. "
            "Return strict JSON with keys: "
            "is_shirt (bool), confidence (0-1), garment_name (string), "
            "brand_hint (string|null), color_hint (string|null), style_tags (string array), "
            "exact_item_hint (string|null), context_terms (string array). "
            "Use brand_hint only if visible text/logo strongly indicates a brand/team. "
            "Only return upper-body garments. "
            "Prefer specific garment_name labels when possible: "
            "hoodie, sweatshirt, t-shirt, polo, button-up shirt, jersey, sweater, tank top. "
            "Use 'shirt' only when specificity is not possible. "
            "Use exact_item_hint only when you are confident about concrete product-style wording "
            "(for example collection names, logo variant, fit style, item naming pattern). "
            "If uncertain, set is_shirt=false and confidence<=0.5."
        )

        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        [{"type": "text", "text": "Describe the primary top garment can be shirt, hoodie, or other top garment. Use all images as alternate crops of the same item."}]
                        + [{"type": "image_url", "image_url": {"url": url}} for url in payload_images]
                    ),
                },
            ],
            "temperature": 0.0,
        }

        data = self._request_with_retry(headers=headers, body=body)
        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw)

        signal = ShirtSignal(
            is_shirt=bool(parsed.get("is_shirt", False)),
            confidence=float(parsed.get("confidence", 0.0)),
            garment_name=str(parsed.get("garment_name") or "shirt").strip(),
            brand_hint=_clean_optional(parsed.get("brand_hint")),
            color_hint=_clean_optional(parsed.get("color_hint")),
            style_tags=[str(x).strip() for x in parsed.get("style_tags", []) if str(x).strip()],
            exact_item_hint=_clean_optional(parsed.get("exact_item_hint")),
            context_terms=[str(x).strip() for x in parsed.get("context_terms", []) if str(x).strip()],
        )
        return signal

    def _refine_garment_type(self, image: Image.Image, signal: ShirtSignal) -> ShirtSignal:
        payload_images = _candidate_data_urls(image)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON with keys garment_name (string) and confidence (0-1). "
                        "Choose exactly one from: hoodie, sweatshirt, t-shirt, polo, button-up shirt, jersey, sweater, tank top, shirt. "
                        "Use visual cues from fit, collar, placket, logo placement, fabric weight, cuff/hem shape, and pockets."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        [
                            {
                                "type": "text",
                                "text": (
                                    "Classify the garment type for the same clothing item. "
                                    f"Current guess is '{signal.garment_name}'. Refine if needed."
                                ),
                            }
                        ]
                        + [{"type": "image_url", "image_url": {"url": url}} for url in payload_images]
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 80,
        }
        try:
            data = self._request_with_retry(headers=headers, body=body)
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
        except Exception:
            return signal

        new_name = _clean_optional(parsed.get("garment_name"))
        new_conf = parsed.get("confidence")
        try:
            conf = float(new_conf) if new_conf is not None else signal.confidence
        except Exception:
            conf = signal.confidence

        if not new_name:
            return signal

        new_name = new_name.lower().strip()
        allowed = {
            "hoodie",
            "sweatshirt",
            "t-shirt",
            "polo",
            "button-up shirt",
            "jersey",
            "sweater",
            "tank top",
            "shirt",
        }
        if new_name not in allowed:
            return signal

        # Override generic "shirt" when model has a confident specific class.
        current = signal.garment_name.lower().strip()
        if current == "shirt" and new_name != "shirt" and conf >= 0.65:
            signal.garment_name = new_name
            signal.confidence = max(signal.confidence, conf)
            return signal

        # Also allow high-confidence correction between specific labels.
        if new_name != current and conf >= 0.8:
            signal.garment_name = new_name
            signal.confidence = max(signal.confidence, conf)
        return signal

    def _infer_brand_hint(self, image: Image.Image) -> str | None:
        payload_images = _candidate_data_urls(image)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON with key brand_hint (string|null). "
                        "Identify visible brand/team/logo text only. "
                        "If not clearly visible, set brand_hint to null."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        [{"type": "text", "text": "What brand or team text/logo is visible on the clothing? Use all images as alternate crops of same garment."}]
                        + [{"type": "image_url", "image_url": {"url": url}} for url in payload_images]
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 80,
        }
        try:
            data = self._request_with_retry(headers=headers, body=body)
        except Exception:
            return None

        try:
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
        except Exception:
            return None
        return _clean_optional(parsed.get("brand_hint"))

    def infer_brand_candidates(self, image: Image.Image, max_candidates: int = 3) -> list[str]:
        payload_images = _candidate_data_urls(image)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON with key candidates (array of strings). "
                        "Provide up to 5 likely brand/team names for the clothing shown. "
                        "If unclear return an empty array."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        [{"type": "text", "text": "List likely clothing brand/team names for this garment."}]
                        + [{"type": "image_url", "image_url": {"url": url}} for url in payload_images]
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 120,
        }
        try:
            data = self._request_with_retry(headers=headers, body=body)
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            values = parsed.get("candidates", [])
        except Exception:
            return []

        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            s = _clean_optional(value)
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
            if len(out) >= max_candidates:
                break
        return out

    def infer_garment_candidates(self, image: Image.Image, max_candidates: int = 3) -> list[str]:
        payload_images = _candidate_data_urls(image)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON with key candidates (array of strings). "
                        "Provide up to 5 likely garment types for the same upper-body item. "
                        "Use only labels from: hoodie, sweatshirt, t-shirt, polo, button-up shirt, jersey, sweater, tank top, shirt."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        [{"type": "text", "text": "List likely garment types ranked by confidence for this item."}]
                        + [{"type": "image_url", "image_url": {"url": url}} for url in payload_images]
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 120,
        }
        try:
            data = self._request_with_retry(headers=headers, body=body)
            raw = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
            values = parsed.get("candidates", [])
        except Exception:
            return []

        allowed = {
            "hoodie",
            "sweatshirt",
            "t-shirt",
            "polo",
            "button-up shirt",
            "jersey",
            "sweater",
            "tank top",
            "shirt",
        }
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            s = _clean_optional(value)
            if not s:
                continue
            k = s.lower().strip()
            if k not in allowed or k in seen:
                continue
            seen.add(k)
            out.append(k)
            if len(out) >= max_candidates:
                break
        return out

    def _request_with_retry(self, headers: dict, body: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            now = time.monotonic()
            wait = self.min_interval_sec - (now - OpenAIShirtAnalyzer._last_call_ts)
            if wait > 0:
                time.sleep(wait)

            try:
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=self.timeout_sec,
                )
                OpenAIShirtAnalyzer._last_call_ts = time.monotonic()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                time.sleep(min(20.0, (2**attempt) + random.uniform(0.1, 0.8)))
                continue

            if resp.status_code == 429:
                text = (resp.text or "").lower()
                if "insufficient_quota" in text or ("quota" in text and "exceeded" in text):
                    raise OpenAIQuotaExceededError(
                        "OpenAI quota exhausted. Please top up credits or use another key."
                    )
                if attempt >= self.max_retries:
                    raise OpenAIQuotaExceededError(
                        "OpenAI rate limit persisted after retries. Please wait and rerun."
                    )
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_s = float(retry_after)
                else:
                    sleep_s = min(30.0, (2**attempt) + random.uniform(0.2, 1.2))
                time.sleep(sleep_s)
                continue

            resp.raise_for_status()
            return resp.json()

        if last_exc:
            raise last_exc
        raise RuntimeError("OpenAI request retry loop exited unexpectedly")


class SerpApiShoppingSearch:
    def __init__(self, api_key: str, timeout_sec: int = 20) -> None:
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    @classmethod
    def from_env(cls) -> "SerpApiShoppingSearch":
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            raise RuntimeError("SERPAPI_API_KEY is required for SerpApiShoppingSearch")
        return cls(api_key=api_key)

    def search(self, query: str, max_results: int = 10) -> list[CatalogProductMatch]:
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "gl": "us",
            "hl": "en",
            "num": max_results,
        }
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=self.timeout_sec)
        resp.raise_for_status()
        data = resp.json()

        out: list[CatalogProductMatch] = []
        for row in data.get("shopping_results", []):
            link = row.get("product_link") or row.get("link")
            title = row.get("title")
            if not link or not title:
                continue

            out.append(
                CatalogProductMatch(
                    title=str(title),
                    product_url=str(link),
                    source=_clean_optional(row.get("source")),
                    price_text=_clean_optional(row.get("price")),
                    price_value=_extract_price_value(row.get("price") or row.get("extracted_price")),
                    image_url=_clean_optional(row.get("thumbnail")),
                    query=query,
                    score=0.0,
                )
            )
        return out


class ShirtCatalogPipeline:
    def __init__(
        self,
        analyzer: ShirtAnalyzer | None = None,
        search: ShoppingSearch | None = None,
        min_confidence: float = 0.7,
    ) -> None:
        self.analyzer = analyzer or OpenAIShirtAnalyzer.from_env()
        self.search = search or SerpApiShoppingSearch.from_env()
        self.min_confidence = min_confidence
        self.max_serp_queries = max(1, int(os.getenv("SHIRT_MAX_SERP_QUERIES", "1")))
        self.enable_serp_fallback_query = os.getenv("SHIRT_ENABLE_SERP_FALLBACK_QUERY", "0") == "1"

    def run(
        self,
        image_input: str | Path | Image.Image,
        top_k: int = 5,
        use_rich_context: bool = False,
    ) -> ShirtCatalogResult:
        image = _load_image(image_input)
        try:
            signal = self.analyzer.analyze(image)
        except OpenAIQuotaExceededError:
            raise
        except requests.HTTPError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc
        except (requests.ConnectionError, requests.Timeout):
            signal = _heuristic_shirt_signal(image)

        if not signal.is_shirt or signal.confidence < self.min_confidence:
            fallback = _heuristic_shirt_signal(image)
            if fallback.confidence >= self.min_confidence:
                signal = fallback
            else:
                return ShirtCatalogResult(status="no_precise_shirt_detected", signal=signal, queries=[], matches=[])

        queries = _build_queries(signal, use_rich_context=use_rich_context)
        merged: dict[str, CatalogProductMatch] = {}
        for query in queries[: self.max_serp_queries]:
            for item in self.search.search(query, max_results=10):
                if item.product_url not in merged:
                    merged[item.product_url] = item

        ranked = _rank_matches(signal, list(merged.values()))
        if not ranked and self.enable_serp_fallback_query and len(queries) > self.max_serp_queries:
            fallback_query = queries[self.max_serp_queries]
            for item in self.search.search(fallback_query, max_results=10):
                if item.product_url not in merged:
                    merged[item.product_url] = item
            ranked = _rank_matches(signal, list(merged.values()))
        return ShirtCatalogResult(
            status="ok" if ranked else "no_products_found",
            signal=signal,
            queries=queries,
            matches=ranked[:top_k],
        )


def _load_image(image_input: str | Path | Image.Image) -> Image.Image:
    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")
    p = Path(image_input)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    return Image.open(p).convert("RGB")


def _image_to_data_url(image: Image.Image) -> str:
    import io

    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _candidate_data_urls(image: Image.Image) -> list[str]:
    img = image.convert("RGB")
    w, h = img.size
    crops: list[Image.Image] = [img]
    # Center garment crop
    crops.append(img.crop((int(w * 0.15), int(h * 0.1), int(w * 0.85), int(h * 0.8))))
    # Upper torso crop where logos/wordmarks often appear
    crops.append(img.crop((int(w * 0.2), int(h * 0.05), int(w * 0.8), int(h * 0.55))))

    urls: list[str] = []
    for c in crops:
        urls.append(_image_to_data_url(c))
    return urls


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    t = str(value).strip()
    return t or None


def _build_queries(
    signal: ShirtSignal,
    use_rich_context: bool = False,
) -> list[str]:
    garment = signal.garment_name.strip() or "shirt"
    base_tokens = [garment]
    if signal.color_hint:
        base_tokens.insert(0, signal.color_hint.strip())
    style = " ".join(signal.style_tags[:2]).strip()
    generic = " ".join([x for x in [*base_tokens, style] if x]).strip() or garment

    queries: list[str] = []
    if signal.brand_hint:
        queries.append(f"{signal.brand_hint} {generic}".strip())
    if use_rich_context:
        if signal.exact_item_hint:
            exact = signal.exact_item_hint.strip()
            queries.append(exact)
            if signal.brand_hint:
                queries.append(f"{signal.brand_hint} {exact}".strip())
        if signal.context_terms:
            context_phrase = " ".join(signal.context_terms[:4]).strip()
            if context_phrase:
                queries.append(context_phrase)
                if signal.brand_hint:
                    queries.append(f"{signal.brand_hint} {context_phrase}".strip())
    queries.append(generic)

    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        k = q.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(q)
    return out


def _rank_matches(
    signal: ShirtSignal,
    matches: list[CatalogProductMatch],
) -> list[CatalogProductMatch]:
    query_tokens = set(_tokenize(" ".join(_build_queries(signal))))
    brand = (signal.brand_hint or "").lower().strip()
    garments = [signal.garment_name.lower().strip()] if signal.garment_name else ["shirt"]
    preferred = next((g for g in garments if g != "shirt"), None)

    ranked: list[CatalogProductMatch] = []
    for item in matches:
        title_l = item.title.lower()
        overlap = len(query_tokens & set(_tokenize(item.title)))
        score = float(overlap)

        if brand:
            score += 5.0 if brand in title_l else -2.5
        if signal.color_hint and signal.color_hint.lower() in title_l:
            score += 1.0
        if item.price_value is not None:
            score += 0.5
        if _is_product_page_url(item.product_url):
            score += 1.5
        if preferred and preferred in title_l:
            score += 2.0
        if preferred and "shirt" in title_l and preferred not in title_l:
            score -= 0.75

        item.score = round(score, 4)
        ranked.append(item)

    ranked.sort(key=lambda x: (x.score, x.price_value is not None), reverse=True)
    return ranked


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def _extract_price_value(raw_price: object) -> float | None:
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    m = re.search(r"(\d+(?:\.\d{1,2})?)", str(raw_price).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _is_product_page_url(url: str) -> bool:
    u = url.lower()
    if "google.com/search" in u or "google.com/shopping" in u:
        return False
    return True


def _heuristic_shirt_signal(image: Image.Image) -> ShirtSignal:
    # Minimal fallback when OpenAI request fails: generic shirt context only.
    return ShirtSignal(
        is_shirt=True,
        confidence=0.70,
        garment_name="shirt",
        brand_hint=None,
        color_hint=None,
        style_tags=[],
    )
