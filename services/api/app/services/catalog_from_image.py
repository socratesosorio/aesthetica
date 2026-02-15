from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
import os
import re
from typing import Any

import logging

import requests
from PIL import Image
from sqlalchemy.orm import Session

from app.models import CatalogRecommendation, CatalogRequest, StyleRecommendation, StyleScore
from app.schemas.catalog import CatalogFromImageResponse, CatalogRecommendationOut
from app.services.notifier import PokeNotifier

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CatalogConfig:
    top_k: int = 5
    openai_model: str = "gpt-4o-mini"
    openai_timeout_sec: int = 25
    serp_timeout_sec: int = 20
    rec_image_timeout_sec: int = 8
    use_rich_context: bool = True


def process_catalog_from_image(
    db: Session,
    image_bytes: bytes,
    filename: str | None,
    content_type: str | None,
    config: CatalogConfig | None = None,
) -> CatalogFromImageResponse:
    cfg = config or CatalogConfig()
    top_k = max(1, min(cfg.top_k, 5))
    req = CatalogRequest(
        original_filename=_clip(filename, 255),
        original_content_type=_clip(content_type, 128),
        original_image_bytes=image_bytes,
        pipeline_status="processing",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    try:
        style_signal = _analyze_style_openai(image_bytes, cfg)
        style_row = StyleScore(
            request_id=req.id,
            image_bytes=image_bytes,
            description=_clip(style_signal.get("description"), 4000) or "",
            casual=_score_0_100(style_signal.get("casual")),
            minimal=_score_0_100(style_signal.get("minimal")),
            structured=_score_0_100(style_signal.get("structured")),
            classic=_score_0_100(style_signal.get("classic")),
            neutral=_score_0_100(style_signal.get("neutral")),
        )
        db.add(style_row)
        db.commit()

        style_ctx = _last_style_context(db, limit=5)
        reco_ctx = _style_recommendation_prompt(style_ctx, cfg)
        style_matches = _search_serp(reco_ctx["search_query"], cfg, max_results=max(10, top_k))
        style_ranked = _rank_style_matches(reco_ctx["search_query"], style_matches)[:top_k]
        rows: list[CatalogRecommendation] = []
        for idx, m in enumerate(style_ranked, start=1):
            cat_row = CatalogRecommendation(
                request_id=req.id,
                rank=idx,
                title=_clip(m.get("title"), 1024) or "",
                product_url=_clip(m.get("product_url"), 2048) or "",
                source=_clip(m.get("source"), 255),
                price_text=_clip(m.get("price_text"), 128),
                price_value=m.get("price_value"),
                query_used=_clip(reco_ctx["search_query"], 2000),
                recommendation_image_url=_clip(m.get("image_url"), 2048),
                recommendation_image_bytes=_download_image_bytes(m.get("image_url"), cfg.rec_image_timeout_sec),
            )
            rows.append(cat_row)
            db.add(cat_row)
            db.add(
                StyleRecommendation(
                    request_id=req.id,
                    rank=idx,
                    title=_clip(m.get("title"), 1024) or "",
                    product_url=_clip(m.get("product_url"), 2048) or "",
                    source=_clip(m.get("source"), 255),
                    price_text=_clip(m.get("price_text"), 128),
                    price_value=m.get("price_value"),
                    query_used=_clip(reco_ctx["search_query"], 2000),
                    recommendation_image_url=_clip(m.get("image_url"), 2048),
                    recommendation_image_bytes=_download_image_bytes(m.get("image_url"), cfg.rec_image_timeout_sec),
                    rationale=_clip(reco_ctx["rationale"], 4000),
                )
            )
        req.pipeline_status = "ok" if rows else "no_products_found"
        req.garment_name = _clip(style_signal.get("garment_name"), 64)
        req.brand_hint = _clip(style_signal.get("brand_hint"), 255)
        req.confidence = float(style_signal.get("confidence", 0.0))
        db.commit()
        db.refresh(req)
        _notify_poke(style_signal, style_ranked)
        return _to_response(req, rows)
    except Exception as exc:
        req.pipeline_status = "pipeline_error"
        req.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        db.refresh(req)
        return _to_response(req, [])


def _notify_poke(signal: dict[str, Any], ranked: list[dict[str, Any]]) -> None:
    """Send a vibey AI-generated message to Poke about what the user just captured."""
    try:
        garment = signal.get("garment_name") or "fit"
        brand = signal.get("brand_hint")
        color = signal.get("color_hint")
        tags = signal.get("style_tags", [])

        # Build context for OpenAI
        details = f"garment: {garment}"
        if brand:
            details += f", brand: {brand}"
        if color:
            details += f", color: {color}"
        if tags:
            details += f", style: {', '.join(tags[:3])}"

        top_match = ""
        image_url = None
        if ranked:
            top = ranked[0]
            title = top.get("title", "")
            price = top.get("price_text")
            product_url = top.get("product_url")
            image_url = top.get("image_url")
            top_match = f"Top match: {title}"
            if price:
                top_match += f" ({price})"
            if product_url:
                top_match += f"\n{product_url}"
            if len(ranked) > 1:
                top_match += f"\n+ {len(ranked) - 1} more options saved"

        opener = _generate_poke_opener(details)

        msg = opener
        if top_match:
            msg += f"\n\n{top_match}"

        PokeNotifier().send(msg, image_url=image_url)
    except Exception:
        logger.exception("poke_notify_failed")


def _generate_poke_opener(garment_details: str) -> str:
    """Use OpenAI to generate a chill, vibey one-liner about the spotted garment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return f"just spotted something fire — {garment_details}"

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a fashion-savvy AI texting a friend about a clothing item they just "
                            "spotted and saved. Write a single short message (1-2 sentences max, under 150 chars). "
                            "Be chill, vibey, gen-z energy. Lowercase. No hashtags. No emojis. "
                            "Sound like a cool friend hyping them up, not a brand. Vary your style every time."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"The user just captured this item: {garment_details}",
                    },
                ],
                "temperature": 1.0,
                "max_tokens": 80,
            },
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.warning("openai_poke_opener_failed, using fallback")
        return f"just spotted something fire — {garment_details}"


def _analyze_image_openai(image_bytes: bytes, cfg: CatalogConfig) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    url = _to_data_url(img)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system = (
        "Return strict JSON with keys: is_shirt (bool), confidence (0-1), garment_name (string), "
        "brand_hint (string|null), color_hint (string|null), style_tags (array of strings), "
        "exact_item_hint (string|null), context_terms (array of strings). "
        "For tops classify as one of hoodie, sweatshirt, t-shirt, polo, button-up shirt, jersey, sweater, tank top, shirt."
    )
    body = {
        "model": cfg.openai_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze the main upper-body clothing item."},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            },
        ],
        "temperature": 0.0,
    }
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=cfg.openai_timeout_sec,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]
    parsed = json.loads(raw)
    return {
        "is_shirt": bool(parsed.get("is_shirt", True)),
        "confidence": float(parsed.get("confidence", 0.7)),
        "garment_name": _clean(parsed.get("garment_name")) or "shirt",
        "brand_hint": _clean(parsed.get("brand_hint")),
        "color_hint": _clean(parsed.get("color_hint")),
        "style_tags": [str(x).strip() for x in parsed.get("style_tags", []) if str(x).strip()],
        "exact_item_hint": _clean(parsed.get("exact_item_hint")),
        "context_terms": [str(x).strip() for x in parsed.get("context_terms", []) if str(x).strip()],
    }


def _search_serp(query: str, cfg: CatalogConfig, max_results: int) -> list[dict[str, Any]]:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is required")
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": api_key,
        "gl": "us",
        "hl": "en",
        "num": max_results,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=cfg.serp_timeout_sec)
    resp.raise_for_status()
    data = resp.json()
    out: list[dict[str, Any]] = []
    for row in data.get("shopping_results", []):
        link = row.get("product_link") or row.get("link")
        title = row.get("title")
        if not link or not title:
            continue
        out.append(
            {
                "title": str(title),
                "product_url": str(link),
                "source": _clean(row.get("source")),
                "price_text": _clean(row.get("price")),
                "price_value": _price_value(row.get("price") or row.get("extracted_price")),
                "image_url": _clean(row.get("thumbnail")),
                "query": query,
            }
        )
    return out


def _analyze_style_openai(image_bytes: bytes, cfg: CatalogConfig) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    url = _to_data_url(img)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system = (
        "Return strict JSON with keys: description (string), garment_name (string), brand_hint (string|null), "
        "confidence (0-1), casual (0-100), minimal (0-100), structured (0-100), classic (0-100), neutral (0-100). "
        "Description should be concise, focused on clothing attributes only."
    )
    body = {
        "model": cfg.openai_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the outfit and score the 5 style attributes from 0 to 100."},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            },
        ],
        "temperature": 0.0,
    }
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=cfg.openai_timeout_sec,
    )
    resp.raise_for_status()
    parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
    return {
        "description": _clean(parsed.get("description")) or "No description",
        "garment_name": _clean(parsed.get("garment_name")) or "shirt",
        "brand_hint": _clean(parsed.get("brand_hint")),
        "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.7)))),
        "casual": parsed.get("casual", 50),
        "minimal": parsed.get("minimal", 50),
        "structured": parsed.get("structured", 50),
        "classic": parsed.get("classic", 50),
        "neutral": parsed.get("neutral", 50),
    }


def _last_style_context(db: Session, limit: int = 5) -> dict[str, Any]:
    rows = db.query(StyleScore).order_by(StyleScore.created_at.desc()).limit(max(1, limit)).all()
    if not rows:
        return {
            "avg": {"casual": 50.0, "minimal": 50.0, "structured": 50.0, "classic": 50.0, "neutral": 50.0},
            "descriptions": [],
        }
    n = float(len(rows))
    avg = {
        "casual": sum(float(r.casual) for r in rows) / n,
        "minimal": sum(float(r.minimal) for r in rows) / n,
        "structured": sum(float(r.structured) for r in rows) / n,
        "classic": sum(float(r.classic) for r in rows) / n,
        "neutral": sum(float(r.neutral) for r in rows) / n,
    }
    descriptions = [r.description for r in reversed(rows)]
    return {"avg": avg, "descriptions": descriptions}


def _style_recommendation_prompt(style_ctx: dict[str, Any], cfg: CatalogConfig) -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    system = (
        "Return strict JSON with keys: search_query (string), rationale (string). "
        "search_query should be a concise shopping query for similar clothing items."
    )
    user_text = (
        f"Average scores: {json.dumps(style_ctx.get('avg', {}))}. "
        f"Last descriptions: {json.dumps(style_ctx.get('descriptions', []))}. "
        "Recommend similar clothing to search for."
    )
    body = {
        "model": cfg.openai_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
    }
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=cfg.openai_timeout_sec,
    )
    resp.raise_for_status()
    parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
    return {
        "search_query": _clean(parsed.get("search_query")) or "minimal classic casual neutral clothing",
        "rationale": _clean(parsed.get("rationale")) or "Recommended from score and description profile.",
    }


def _rank_style_matches(query: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    q_tokens = set(_tokens(query))
    scored: list[tuple[float, dict[str, Any]]] = []
    for m in matches:
        title = m.get("title") or ""
        score = float(len(q_tokens & set(_tokens(title))))
        if m.get("price_value") is not None:
            score += 0.3
        if "google.com/search" not in (m.get("product_url") or "").lower():
            score += 0.8
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]


def _download_image_bytes(url: str | None, timeout_sec: int) -> bytes | None:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=timeout_sec)
        r.raise_for_status()
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "image" not in ctype:
            return None
        return r.content
    except Exception:
        return None


def _to_data_url(image: Image.Image) -> str:
    import base64

    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clip(v: str | None, n: int) -> str | None:
    if v is None:
        return None
    return v[:n]


def _price_value(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"(\d+(?:\.\d{1,2})?)", str(raw).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _score_0_100(value: Any) -> float:
    try:
        v = float(value)
    except Exception:
        return 50.0
    if v < 0:
        return 0.0
    if v > 100:
        return 100.0
    return round(v, 2)


def _to_response(req: CatalogRequest, rows: list[CatalogRecommendation]) -> CatalogFromImageResponse:
    rows = sorted(rows, key=lambda x: x.rank)
    return CatalogFromImageResponse(
        request_id=req.id,
        created_at=req.created_at,
        pipeline_status=req.pipeline_status,
        garment_name=req.garment_name,
        brand_hint=req.brand_hint,
        confidence=req.confidence,
        error=req.error,
        recommendation_count=len(rows),
        recommendations=[
            CatalogRecommendationOut(
                rank=r.rank,
                title=r.title,
                product_url=r.product_url,
                source=r.source,
                price_text=r.price_text,
                price_value=r.price_value,
                query_used=r.query_used,
                recommendation_image_url=r.recommendation_image_url,
                has_recommendation_image_bytes=r.recommendation_image_bytes is not None,
            )
            for r in rows
        ],
    )
