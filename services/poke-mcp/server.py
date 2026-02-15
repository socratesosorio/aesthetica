"""Aesthetica Poke MCP Server - optimized MCP tools for texting LLM."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from typing import Any

sys.path.insert(0, "/app/services/api")
sys.path.insert(0, "/app/services/ml")

import httpx
import requests
from fastmcp import FastMCP
from sqlalchemy import desc, func

from app.db.session import SessionLocal
from app.models import (
    CatalogRecommendation,
    CatalogRequest,
    Product,
    StyleRecommendation,
    StyleScore,
    User,
)
from app.services.catalog_from_image import (
    CatalogConfig,
    _analyze_style_openai,
    _last_style_context,
    _search_serp,
    _style_recommendation_prompt,
)
from app.services.web_product_search import SerpApiWebProductSearcher
from ml_core.embeddings import get_embedder
from ml_core.retrieval import CATEGORIES, get_catalog

from mcp_cache import TTLCache
from mcp_utils import clip_text, clamp_int, elapsed_ms, error_response, now_ms, ok_response, to_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("poke-mcp")

mcp = FastMCP("Aesthetica - AI Fashion Intelligence")

STYLE_AXES = ["casual", "minimal", "structured", "classic", "neutral"]
CACHE_TTL_SECONDS = int(os.getenv("POKE_MCP_CACHE_TTL_SECONDS", "60"))

SEARCH_CACHE: TTLCache[list[dict[str, Any]]] = TTLCache(ttl_seconds=CACHE_TTL_SECONDS, max_entries=512)
STYLE_PROMPT_CACHE: TTLCache[dict[str, str]] = TTLCache(ttl_seconds=CACHE_TTL_SECONDS, max_entries=256)
OUTFIT_PLAN_CACHE: TTLCache[dict[str, Any]] = TTLCache(ttl_seconds=CACHE_TTL_SECONDS, max_entries=128)
ANALYZE_CACHE: TTLCache[dict[str, Any]] = TTLCache(ttl_seconds=CACHE_TTL_SECONDS, max_entries=128)

HTTP_CLIENT = httpx.Client(timeout=15.0, follow_redirects=True)

DEMO_USER_ID: str | None = None


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _scores_from_style_row(style_row: StyleScore | None) -> dict[str, float]:
    if style_row is None:
        return {axis: 50.0 for axis in STYLE_AXES}
    return {axis: _score_0_100(getattr(style_row, axis, 50.0)) for axis in STYLE_AXES}


def _next_actions_for_analysis(has_products: bool) -> list[dict[str, str]]:
    actions = [
        {"tool": "get_style_scores", "reason": "Read trend and delta against older analyses."},
        {"tool": "get_my_style", "reason": "Get a concise identity-level style summary."},
    ]
    if not has_products:
        actions.insert(0, {"tool": "find_similar_products", "reason": "Fetch product options for this style."})
    return actions


def _get_demo_user_id() -> str | None:
    global DEMO_USER_ID
    if DEMO_USER_ID is None:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "demo@aesthetica.dev").first()
            DEMO_USER_ID = user.id if user else None
            if DEMO_USER_ID:
                logger.info("demo_user_resolved id=%s", DEMO_USER_ID)
            else:
                logger.warning("demo_user_not_found")
        except Exception:
            logger.exception("demo_user_lookup_failed")
        finally:
            db.close()
    return DEMO_USER_ID


def _cached_serp_search(query: str, cfg: CatalogConfig, max_results: int) -> tuple[list[dict[str, Any]], bool]:
    clean_query = " ".join(query.strip().split())
    key = _hash_payload({"kind": "serp", "query": clean_query.lower(), "max_results": max_results})

    def _factory() -> list[dict[str, Any]]:
        return _search_serp(clean_query, cfg, max_results=max_results)

    return SEARCH_CACHE.get_or_set(key, _factory)


def _cached_style_prompt(style_ctx: dict[str, Any], cfg: CatalogConfig, category_hint: str) -> tuple[dict[str, str], bool]:
    avg = style_ctx.get("avg", {})
    payload = {
        "kind": "style_prompt",
        "avg": {axis: round(float(avg.get(axis, 50.0)), 2) for axis in STYLE_AXES},
        "descriptions": [clip_text(d, 200) for d in style_ctx.get("descriptions", [])[-3:]],
        "category_hint": category_hint.strip().lower(),
    }
    key = _hash_payload(payload)

    def _factory() -> dict[str, str]:
        seeded_ctx = dict(style_ctx)
        if category_hint:
            seeded_ctx["category_hint"] = category_hint
        return _style_recommendation_prompt(seeded_ctx, cfg)

    return STYLE_PROMPT_CACHE.get_or_set(key, _factory)


def _cached_outfit_plan(
    occasion: str,
    budget: str,
    style_ctx: dict[str, Any],
    cfg: CatalogConfig,
) -> tuple[dict[str, Any], bool]:
    avg = style_ctx.get("avg", {})
    payload = {
        "kind": "outfit_plan",
        "occasion": occasion.strip().lower(),
        "budget": budget.strip().lower(),
        "avg": {axis: round(float(avg.get(axis, 50.0)), 2) for axis in STYLE_AXES},
        "descriptions": [clip_text(d, 180) for d in style_ctx.get("descriptions", [])[-3:]],
        "model": cfg.openai_model,
    }
    key = _hash_payload(payload)

    def _factory() -> dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")

        budget_note = f" Budget constraint: {budget}." if budget else ""
        system_prompt = (
            "You are a fashion stylist AI. Return strict JSON with keys: "
            "pieces (array of objects with 'role' and 'search_query'), outfit_rationale (string). "
            "Each piece role must be one of: top, bottom, shoes, accessory. "
            "Use concise, shoppable search queries. Generate 2-4 cohesive pieces."
        )
        user_prompt = (
            f"Build an outfit for: {occasion}.{budget_note}\n"
            f"User style profile: {json.dumps(style_ctx.get('avg', {}))}\n"
            f"Recent descriptions: {json.dumps(style_ctx.get('descriptions', [])[-3:])}"
        )

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": cfg.openai_model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.35,
            },
            timeout=cfg.openai_timeout_sec,
        )
        resp.raise_for_status()
        return json.loads(resp.json()["choices"][0]["message"]["content"])

    return OUTFIT_PLAN_CACHE.get_or_set(key, _factory)


def _serialize_serp_item(item: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "title": clip_text(item.get("title"), 180),
        "price_text": clip_text(item.get("price_text"), 48) or None,
        "source": clip_text(item.get("source"), 64) or None,
        "url": clip_text(item.get("product_url"), 512),
    }


def _serialize_style_reco(rec: StyleRecommendation) -> dict[str, Any]:
    return {
        "rank": rec.rank,
        "title": clip_text(rec.title, 180),
        "price_text": clip_text(rec.price_text, 48) if rec.price_text else None,
        "source": clip_text(rec.source, 64) if rec.source else None,
        "url": clip_text(rec.product_url, 512),
    }


def _top_axes(scores: dict[str, float], n: int = 2) -> list[dict[str, Any]]:
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [{"axis": axis, "score": round(val, 2)} for axis, val in ranked[:n]]


def _create_catalog_request(db, image_bytes: bytes, filename: str, content_type: str) -> CatalogRequest:
    req = CatalogRequest(
        original_filename=clip_text(filename, 255) or "outfit.jpg",
        original_content_type=clip_text(content_type, 128) or "image/jpeg",
        original_image_bytes=image_bytes,
        pipeline_status="processing",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _persist_analysis(
    db,
    image_bytes: bytes,
    filename: str,
    content_type: str,
    mode: str,
    include_products: bool,
    max_products: int,
) -> dict[str, Any]:
    cfg = CatalogConfig()
    req = _create_catalog_request(db, image_bytes=image_bytes, filename=filename, content_type=content_type)

    try:
        signal = _analyze_style_openai(image_bytes, cfg)
        style_row = StyleScore(
            request_id=req.id,
            image_bytes=None,
            description=clip_text(signal.get("description"), 4000),
            casual=_score_0_100(signal.get("casual")),
            minimal=_score_0_100(signal.get("minimal")),
            structured=_score_0_100(signal.get("structured")),
            classic=_score_0_100(signal.get("classic")),
            neutral=_score_0_100(signal.get("neutral")),
        )
        db.add(style_row)
        db.commit()
        db.refresh(style_row)

        recommendations: list[dict[str, Any]] = []
        rationale = ""
        search_query = ""

        if include_products:
            style_ctx = _last_style_context(db, limit=5)
            reco_ctx, _ = _cached_style_prompt(style_ctx, cfg=cfg, category_hint="")
            rationale = clip_text(reco_ctx.get("rationale"), 360)
            search_query = clip_text(reco_ctx.get("search_query"), 240)

            web_results, _ = _cached_serp_search(search_query, cfg=cfg, max_results=max(5, max_products))
            for idx, item in enumerate(web_results[:max_products], start=1):
                title = clip_text(item.get("title"), 1024)
                url = clip_text(item.get("product_url"), 2048)
                if not title or not url:
                    continue

                style_rec = StyleRecommendation(
                    request_id=req.id,
                    rank=idx,
                    title=title,
                    product_url=url,
                    source=clip_text(item.get("source"), 255) or None,
                    price_text=clip_text(item.get("price_text"), 128) or None,
                    price_value=item.get("price_value"),
                    query_used=search_query,
                    recommendation_image_url=clip_text(item.get("image_url"), 2048) or None,
                    recommendation_image_bytes=None,
                    rationale=rationale or None,
                )
                cat_rec = CatalogRecommendation(
                    request_id=req.id,
                    rank=idx,
                    title=title,
                    product_url=url,
                    source=clip_text(item.get("source"), 255) or None,
                    price_text=clip_text(item.get("price_text"), 128) or None,
                    price_value=item.get("price_value"),
                    query_used=search_query,
                    recommendation_image_url=clip_text(item.get("image_url"), 2048) or None,
                    recommendation_image_bytes=None,
                )
                db.add(style_rec)
                db.add(cat_rec)
                recommendations.append(_serialize_serp_item(item, idx))

            db.commit()

        req.pipeline_status = "ok" if (not include_products or recommendations) else "no_products_found"
        req.garment_name = clip_text(signal.get("garment_name"), 64) or "outfit"
        req.brand_hint = clip_text(signal.get("brand_hint"), 255) or None
        req.confidence = float(signal.get("confidence", 0.0))
        req.error = None
        db.commit()
        db.refresh(req)

        scores = _scores_from_style_row(style_row)
        return {
            "request_id": req.id,
            "pipeline_status": req.pipeline_status,
            "detected_item": {
                "garment_name": req.garment_name,
                "brand_hint": req.brand_hint,
                "confidence": round(float(req.confidence or 0.0), 3),
            },
            "summary": clip_text(style_row.description, 280),
            "scores": scores,
            "top_signals": _top_axes(scores, n=2),
            "products": recommendations,
            "search_query": search_query or None,
            "rationale": rationale or None,
            "mode": mode,
            "persisted": True,
        }
    except Exception as exc:
        db.rollback()
        req.pipeline_status = "pipeline_error"
        req.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        db.refresh(req)
        return {
            "request_id": req.id,
            "pipeline_status": req.pipeline_status,
            "error": clip_text(req.error, 240),
            "mode": mode,
            "persisted": True,
        }


@mcp.tool()
def analyze_outfit(
    image_url: str,
    mode: str = "fast",
    include_products: bool = False,
    max_products: int = 3,
    persist: bool = True,
) -> dict[str, Any]:
    """Analyze an outfit image URL and persist style results. Returns compact JSON."""
    intent = "analyze_outfit"
    t0 = now_ms()
    timings: dict[str, int] = {}

    mode_norm = mode.strip().lower()
    if mode_norm not in {"fast", "full"}:
        mode_norm = "fast"

    include_products_norm = include_products or mode_norm == "full"
    max_products_norm = clamp_int(max_products, 1, 8)

    if not image_url.startswith(("http://", "https://")):
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "invalid_image_url", "image_url must be http(s)", timings)

    cache_key = _hash_payload(
        {
            "kind": "analyze",
            "image_url": image_url,
            "mode": mode_norm,
            "include_products": include_products_norm,
            "max_products": max_products_norm,
            "persist": bool(persist),
        }
    )
    cached = ANALYZE_CACHE.get(cache_key)
    if cached is not None:
        data = dict(cached)
        data["cache_hit"] = True
        timings["total"] = elapsed_ms(t0)
        return ok_response(intent, data=data, timing_ms=timings, next_actions=_next_actions_for_analysis(bool(data.get("products"))))

    try:
        t_fetch = now_ms()
        response = HTTP_CLIENT.get(image_url)
        response.raise_for_status()
        image_bytes = response.content
        timings["image_fetch"] = elapsed_ms(t_fetch)
    except Exception:
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "image_download_failed", "Failed to download image.", timings)

    if not image_bytes:
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "empty_image", "Downloaded image payload is empty.", timings)

    content_type = response.headers.get("content-type", "image/jpeg")
    filename = image_url.rsplit("/", 1)[-1][:255] or "outfit.jpg"

    db = SessionLocal()
    try:
        t_analysis = now_ms()
        data = _persist_analysis(
            db,
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
            mode=mode_norm,
            include_products=include_products_norm,
            max_products=max_products_norm,
        )
        timings["analysis_persist"] = elapsed_ms(t_analysis)

        if data.get("pipeline_status") == "pipeline_error":
            timings["total"] = elapsed_ms(t0)
            return error_response(
                intent,
                "analysis_failed",
                data.get("error") or "Pipeline failed.",
                timings,
                data={"request_id": data.get("request_id"), "mode": mode_norm, "persisted": True},
            )

        data["cache_hit"] = False
        ANALYZE_CACHE.set(cache_key, data)

        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data=data,
            timing_ms=timings,
            next_actions=_next_actions_for_analysis(bool(data.get("products"))),
        )
    except Exception:
        logger.exception("analyze_outfit_failed")
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "analysis_failed", "Failed to analyze image.", timings)
    finally:
        db.close()


@mcp.tool()
def find_similar_products(
    query: str,
    category: str = "top",
    include_web: bool = False,
    limit: int = 5,
) -> dict[str, Any]:
    """Search local catalog embeddings and optional web results with compact JSON output."""
    intent = "find_similar_products"
    t0 = now_ms()
    timings: dict[str, int] = {}

    clean_query = clip_text(query, 160)
    if not clean_query:
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "invalid_query", "query is required", timings)

    category_norm = category.strip().lower() or "top"
    limit_norm = clamp_int(limit, 1, 10)

    catalog_hits: list[dict[str, Any]] = []
    used_web = False

    try:
        t_catalog = now_ms()
        catalog = get_catalog()
        if catalog.is_ready() and category_norm in CATEGORIES:
            embedding = get_embedder().text_embedding(clean_query)
            results = catalog.query(category_norm, embedding, top_k=limit_norm)
            if results:
                db = SessionLocal()
                try:
                    product_ids = [r.product_id for r in results]
                    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
                    by_id = {p.id: p for p in products}

                    for r in results:
                        p = by_id.get(r.product_id)
                        if p is None:
                            continue
                        catalog_hits.append(
                            {
                                "rank": r.rank,
                                "title": clip_text(p.title, 180),
                                "brand": clip_text(p.brand, 80),
                                "price": round(float(p.price), 2) if p.price is not None else None,
                                "currency": clip_text(p.currency, 12) if p.currency else None,
                                "similarity": round(float(r.similarity), 4),
                                "source": "catalog",
                                "url": clip_text(p.product_url, 512),
                            }
                        )
                finally:
                    db.close()
        timings["catalog"] = elapsed_ms(t_catalog)
    except Exception:
        logger.exception("find_similar_products_catalog_failed")

    web_hits: list[dict[str, Any]] = []
    if include_web or not catalog_hits:
        try:
            used_web = True
            t_web = now_ms()
            cfg = CatalogConfig()
            serp_items, cache_hit = _cached_serp_search(clean_query, cfg, max_results=limit_norm)
            web_hits = [_serialize_serp_item(item, i) for i, item in enumerate(serp_items[:limit_norm], start=1)]
            timings["web"] = elapsed_ms(t_web)
            timings["web_cache_hit"] = 1 if cache_hit else 0
        except Exception:
            logger.exception("find_similar_products_web_failed")

    timings["total"] = elapsed_ms(t0)
    return ok_response(
        intent,
        data={
            "query": clean_query,
            "category": category_norm,
            "catalog_results": catalog_hits,
            "web_results": web_hits,
            "used_web": used_web,
        },
        timing_ms=timings,
        next_actions=[{"tool": "search_clothes", "reason": "Run a focused shopping search if you want more options."}],
    )


@mcp.tool()
def get_style_scores(limit: int = 5) -> dict[str, Any]:
    """Return recent style scores in compact trend format."""
    intent = "get_style_scores"
    t0 = now_ms()
    timings: dict[str, int] = {}

    limit_norm = clamp_int(limit, 1, 30)
    db = SessionLocal()
    try:
        rows = (
            db.query(
                StyleScore.id,
                StyleScore.request_id,
                StyleScore.created_at,
                StyleScore.description,
                StyleScore.casual,
                StyleScore.minimal,
                StyleScore.structured,
                StyleScore.classic,
                StyleScore.neutral,
            )
            .order_by(desc(StyleScore.created_at))
            .limit(limit_norm)
            .all()
        )

        if not rows:
            timings["total"] = elapsed_ms(t0)
            return ok_response(intent, data={"history": [], "message": "No style scores yet."}, timing_ms=timings)

        history: list[dict[str, Any]] = []
        for row in rows:
            scores = {
                "casual": _score_0_100(row.casual),
                "minimal": _score_0_100(row.minimal),
                "structured": _score_0_100(row.structured),
                "classic": _score_0_100(row.classic),
                "neutral": _score_0_100(row.neutral),
            }
            history.append(
                {
                    "id": row.id,
                    "request_id": row.request_id,
                    "created_at": to_iso(row.created_at),
                    "summary": clip_text(row.description, 160) or None,
                    "scores": scores,
                }
            )

        latest = history[0]["scores"]
        oldest = history[-1]["scores"]
        avg: dict[str, float] = {}
        for axis in STYLE_AXES:
            avg[axis] = round(sum(h["scores"][axis] for h in history) / len(history), 2)

        delta_vs_oldest = {axis: round(latest[axis] - oldest[axis], 2) for axis in STYLE_AXES}

        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data={
                "count": len(history),
                "latest": latest,
                "avg_last_n": avg,
                "delta_vs_oldest": delta_vs_oldest,
                "history_brief": history,
            },
            timing_ms=timings,
            next_actions=[{"tool": "get_my_style", "reason": "Convert recent scores into a concise identity summary."}],
        )
    finally:
        db.close()


@mcp.tool()
def get_catalog_results(limit: int = 5) -> dict[str, Any]:
    """Return recent catalog analyses with compact recommendation summaries."""
    intent = "get_catalog_results"
    t0 = now_ms()
    timings: dict[str, int] = {}

    limit_norm = clamp_int(limit, 1, 25)
    db = SessionLocal()
    try:
        requests_rows = (
            db.query(
                CatalogRequest.id,
                CatalogRequest.created_at,
                CatalogRequest.pipeline_status,
                CatalogRequest.garment_name,
                CatalogRequest.brand_hint,
                CatalogRequest.confidence,
                CatalogRequest.error,
            )
            .filter(CatalogRequest.pipeline_status != "processing")
            .order_by(desc(CatalogRequest.created_at))
            .limit(limit_norm)
            .all()
        )

        if not requests_rows:
            timings["total"] = elapsed_ms(t0)
            return ok_response(intent, data={"results": []}, timing_ms=timings)

        request_ids = [row.id for row in requests_rows]

        score_rows = (
            db.query(
                StyleScore.request_id,
                StyleScore.created_at,
                StyleScore.description,
                StyleScore.casual,
                StyleScore.minimal,
                StyleScore.structured,
                StyleScore.classic,
                StyleScore.neutral,
            )
            .filter(StyleScore.request_id.in_(request_ids))
            .order_by(desc(StyleScore.created_at))
            .all()
        )
        score_by_request: dict[str, Any] = {}
        for row in score_rows:
            if row.request_id in score_by_request:
                continue
            score_by_request[row.request_id] = row

        style_rec_rows = (
            db.query(
                StyleRecommendation.request_id,
                StyleRecommendation.rank,
                StyleRecommendation.title,
                StyleRecommendation.price_text,
                StyleRecommendation.source,
                StyleRecommendation.product_url,
                StyleRecommendation.rationale,
            )
            .filter(StyleRecommendation.request_id.in_(request_ids))
            .order_by(StyleRecommendation.request_id, StyleRecommendation.rank)
            .all()
        )
        style_recs_by_request: dict[str, list[Any]] = defaultdict(list)
        rationale_by_request: dict[str, str] = {}
        for row in style_rec_rows:
            style_recs_by_request[row.request_id].append(row)
            if row.rationale and row.request_id not in rationale_by_request:
                rationale_by_request[row.request_id] = row.rationale

        out: list[dict[str, Any]] = []
        for req in requests_rows:
            style_row = score_by_request.get(req.id)
            scores = {
                "casual": _score_0_100(style_row.casual) if style_row else 50.0,
                "minimal": _score_0_100(style_row.minimal) if style_row else 50.0,
                "structured": _score_0_100(style_row.structured) if style_row else 50.0,
                "classic": _score_0_100(style_row.classic) if style_row else 50.0,
                "neutral": _score_0_100(style_row.neutral) if style_row else 50.0,
            }
            products = []
            for rec in style_recs_by_request.get(req.id, [])[:3]:
                products.append(
                    {
                        "rank": rec.rank,
                        "title": clip_text(rec.title, 160),
                        "price_text": clip_text(rec.price_text, 48) if rec.price_text else None,
                        "source": clip_text(rec.source, 64) if rec.source else None,
                        "url": clip_text(rec.product_url, 512),
                    }
                )

            out.append(
                {
                    "request_id": req.id,
                    "created_at": to_iso(req.created_at),
                    "status": req.pipeline_status,
                    "detected_item": {
                        "garment_name": req.garment_name,
                        "brand_hint": req.brand_hint,
                        "confidence": round(float(req.confidence or 0.0), 3),
                    },
                    "summary": clip_text(style_row.description, 180) if style_row and style_row.description else None,
                    "scores": scores,
                    "rationale": clip_text(rationale_by_request.get(req.id), 220) or None,
                    "products": products,
                    "error": clip_text(req.error, 200) if req.error else None,
                }
            )

        timings["total"] = elapsed_ms(t0)
        return ok_response(intent, data={"results": out}, timing_ms=timings)
    finally:
        db.close()


@mcp.tool()
def get_style_recommendations(
    category_hint: str = "",
    limit: int = 5,
    include_web: bool = True,
) -> dict[str, Any]:
    """Generate style-based product recommendations from rolling profile context."""
    intent = "get_style_recommendations"
    t0 = now_ms()
    timings: dict[str, int] = {}

    limit_norm = clamp_int(limit, 1, 10)
    category_clean = clip_text(category_hint, 80)

    db = SessionLocal()
    try:
        cfg = CatalogConfig()
        style_ctx = _last_style_context(db, limit=5)
        if not style_ctx.get("descriptions"):
            timings["total"] = elapsed_ms(t0)
            return ok_response(intent, data={"message": "No style history yet.", "recommendations": []}, timing_ms=timings)

        t_prompt = now_ms()
        reco_ctx, prompt_cache_hit = _cached_style_prompt(style_ctx, cfg=cfg, category_hint=category_clean)
        timings["prompt"] = elapsed_ms(t_prompt)
        timings["prompt_cache_hit"] = 1 if prompt_cache_hit else 0

        search_query = reco_ctx.get("search_query", "").strip()
        if category_clean and category_clean.lower() not in search_query.lower():
            search_query = f"{category_clean} {search_query}".strip()

        products: list[dict[str, Any]] = []
        search_cache_hit = False
        if include_web:
            t_web = now_ms()
            web_results, search_cache_hit = _cached_serp_search(search_query, cfg, max_results=limit_norm)
            products = [_serialize_serp_item(item, i) for i, item in enumerate(web_results[:limit_norm], start=1)]
            timings["web"] = elapsed_ms(t_web)

        avg = style_ctx.get("avg", {})
        profile = {axis: round(float(avg.get(axis, 50.0)), 2) for axis in STYLE_AXES}

        timings["web_cache_hit"] = 1 if search_cache_hit else 0
        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data={
                "profile": profile,
                "search_query": clip_text(search_query, 220),
                "rationale": clip_text(reco_ctx.get("rationale"), 220),
                "recommendations": products,
            },
            timing_ms=timings,
            next_actions=[{"tool": "search_clothes", "reason": "Run additional targeted shopping query."}],
        )
    except Exception:
        logger.exception("style_recommendations_failed")
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "style_recommendations_failed", "Failed to generate style recommendations.", timings)
    finally:
        db.close()


@mcp.tool()
def get_wardrobe_stats() -> dict[str, Any]:
    """Return aggregate wardrobe stats in compact format."""
    intent = "get_wardrobe_stats"
    t0 = now_ms()
    timings: dict[str, int] = {}

    db = SessionLocal()
    try:
        catalog_count = db.query(CatalogRequest).filter(CatalogRequest.pipeline_status != "processing").count()
        style_score_count = db.query(StyleScore).count()

        last_scan = (
            db.query(CatalogRequest.created_at)
            .filter(CatalogRequest.pipeline_status != "processing")
            .order_by(desc(CatalogRequest.created_at))
            .first()
        )

        avg_scores = {axis: 50.0 for axis in STYLE_AXES}
        if style_score_count > 0:
            avgs = db.query(
                func.avg(StyleScore.casual),
                func.avg(StyleScore.minimal),
                func.avg(StyleScore.structured),
                func.avg(StyleScore.classic),
                func.avg(StyleScore.neutral),
            ).one()
            for axis, value in zip(STYLE_AXES, avgs):
                avg_scores[axis] = round(float(value or 50.0), 2)

        catalog_rows = (
            db.query(CatalogRequest.garment_name, CatalogRequest.brand_hint)
            .filter(CatalogRequest.pipeline_status != "processing")
            .all()
        )
        garment_counts = Counter(r.garment_name for r in catalog_rows if r.garment_name)
        brand_counts = Counter(r.brand_hint for r in catalog_rows if r.brand_hint)

        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data={
                "catalog_scans": catalog_count,
                "style_scores_recorded": style_score_count,
                "last_scan_at": to_iso(last_scan.created_at) if last_scan else None,
                "average_scores": avg_scores,
                "top_garments": [{"name": g, "count": c} for g, c in garment_counts.most_common(5)],
                "top_brands": [{"name": b, "count": c} for b, c in brand_counts.most_common(5)],
            },
            timing_ms=timings,
        )
    finally:
        db.close()


@mcp.tool()
def get_my_style() -> dict[str, Any]:
    """Return a compact summary of current style identity."""
    intent = "get_my_style"
    t0 = now_ms()
    timings: dict[str, int] = {}

    db = SessionLocal()
    try:
        style_ctx = _last_style_context(db, limit=10)
        descriptions = style_ctx.get("descriptions", [])
        if not descriptions:
            timings["total"] = elapsed_ms(t0)
            return ok_response(intent, data={"message": "No style data yet."}, timing_ms=timings)

        avg = {axis: round(float(style_ctx.get("avg", {}).get(axis, 50.0)), 2) for axis in STYLE_AXES}
        dominant = _top_axes(avg, n=3)

        catalog_rows = (
            db.query(CatalogRequest.garment_name, CatalogRequest.brand_hint)
            .filter(CatalogRequest.pipeline_status != "processing")
            .order_by(desc(CatalogRequest.created_at))
            .limit(50)
            .all()
        )
        garment_counts = Counter(r.garment_name for r in catalog_rows if r.garment_name)
        brand_counts = Counter(r.brand_hint for r in catalog_rows if r.brand_hint)

        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data={
                "profile": avg,
                "dominant_axes": dominant,
                "recent_descriptions": [clip_text(d, 170) for d in descriptions[-5:] if d],
                "top_garments": [{"name": g, "count": c} for g, c in garment_counts.most_common(5)],
                "top_brands": [{"name": b, "count": c} for b, c in brand_counts.most_common(5)],
            },
            timing_ms=timings,
            next_actions=[{"tool": "get_style_recommendations", "reason": "Turn profile signals into shopping suggestions."}],
        )
    finally:
        db.close()


@mcp.tool()
def search_clothes(query: str, category: str = "top", max_results: int = 5) -> dict[str, Any]:
    """Search shopping results with compact JSON output."""
    intent = "search_clothes"
    t0 = now_ms()
    timings: dict[str, int] = {}

    clean_query = clip_text(query, 160)
    if not clean_query:
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "invalid_query", "query is required", timings)

    category_norm = category.strip().lower() or "top"
    limit_norm = clamp_int(max_results, 1, 10)

    try:
        t_search = now_ms()
        searcher = SerpApiWebProductSearcher()
        attributes = {"query_text": clean_query}
        results = searcher.search(category=category_norm, attributes=attributes, limit=limit_norm)
        timings["search"] = elapsed_ms(t_search)

        payload: list[dict[str, Any]] = []
        if results:
            for i, cand in enumerate(results[:limit_norm], start=1):
                payload.append(
                    {
                        "rank": i,
                        "title": clip_text(cand.title, 180),
                        "brand": clip_text(cand.brand, 80),
                        "price": round(float(cand.price), 2) if cand.price is not None else None,
                        "currency": cand.currency,
                        "url": clip_text(cand.product_url, 512),
                        "source": cand.provider,
                    }
                )
        else:
            cfg = CatalogConfig()
            serp_items, cache_hit = _cached_serp_search(clean_query, cfg, max_results=limit_norm)
            payload = [_serialize_serp_item(item, i) for i, item in enumerate(serp_items[:limit_norm], start=1)]
            timings["fallback_cache_hit"] = 1 if cache_hit else 0

        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data={
                "query": clean_query,
                "category": category_norm,
                "results": payload,
            },
            timing_ms=timings,
        )
    except Exception:
        logger.exception("search_clothes_failed")
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "search_failed", "Search failed.", timings)


@mcp.tool()
def build_outfit(
    occasion: str,
    budget: str = "",
    fast: bool = True,
    max_results_per_piece: int = 2,
) -> dict[str, Any]:
    """Build a shopping-ready outfit plan based on style profile and occasion."""
    intent = "build_outfit"
    t0 = now_ms()
    timings: dict[str, int] = {}

    occasion_clean = clip_text(occasion, 120)
    if not occasion_clean:
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "invalid_occasion", "occasion is required", timings)

    limit_norm = clamp_int(max_results_per_piece, 1, 3 if fast else 4)

    db = SessionLocal()
    try:
        cfg = CatalogConfig()
        style_ctx = _last_style_context(db, limit=5)
        if not style_ctx.get("descriptions"):
            timings["total"] = elapsed_ms(t0)
            return ok_response(intent, data={"message": "No style history yet."}, timing_ms=timings)

        t_plan = now_ms()
        outfit_plan, plan_cache_hit = _cached_outfit_plan(occasion_clean, budget, style_ctx, cfg)
        timings["plan"] = elapsed_ms(t_plan)
        timings["plan_cache_hit"] = 1 if plan_cache_hit else 0

        pieces = outfit_plan.get("pieces", [])
        if not isinstance(pieces, list):
            pieces = []
        pieces = pieces[: (3 if fast else 4)]

        piece_results: list[dict[str, Any]] = []
        search_cache_hits = 0
        for piece in pieces:
            role = clip_text(piece.get("role"), 32).lower() or "item"
            query_text = clip_text(piece.get("search_query"), 180)
            if not query_text:
                continue
            if budget:
                query_text = clip_text(f"{query_text} {budget}", 220)

            web_results, cache_hit = _cached_serp_search(query_text, cfg, max_results=max(limit_norm, 2))
            if cache_hit:
                search_cache_hits += 1

            options = [_serialize_serp_item(item, i) for i, item in enumerate(web_results[:limit_norm], start=1)]
            piece_results.append({"role": role, "query": query_text, "options": options})

        avg = style_ctx.get("avg", {})
        profile = {axis: round(float(avg.get(axis, 50.0)), 2) for axis in STYLE_AXES}

        timings["search_cache_hits"] = search_cache_hits
        timings["total"] = elapsed_ms(t0)
        return ok_response(
            intent,
            data={
                "occasion": occasion_clean,
                "budget": clip_text(budget, 80) or None,
                "fast_mode": bool(fast),
                "concept": clip_text(outfit_plan.get("outfit_rationale"), 220),
                "pieces": piece_results,
                "profile_snapshot": profile,
            },
            timing_ms=timings,
            next_actions=[{"tool": "search_clothes", "reason": "Expand one specific piece with a focused query."}],
        )
    except Exception:
        logger.exception("build_outfit_failed")
        timings["total"] = elapsed_ms(t0)
        return error_response(intent, "build_outfit_failed", "Failed to build outfit.", timings)
    finally:
        db.close()


if __name__ == "__main__":
    _get_demo_user_id()
    get_catalog()
    logger.info("starting Aesthetica MCP server on port 8787")
    mcp.run(transport="sse", host="0.0.0.0", port=8787)
