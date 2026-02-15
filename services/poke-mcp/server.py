"""Aesthetica Poke MCP Server — exposes fashion intelligence as MCP tools."""
from __future__ import annotations

import sys

sys.path.insert(0, "/app/services/api")
sys.path.insert(0, "/app/services/ml")

import logging
from datetime import datetime, timedelta, timezone

import httpx
import numpy as np
from fastmcp import FastMCP
from sqlalchemy import desc, func

from app.db.session import SessionLocal
from app.models import (
    Capture,
    CatalogRecommendation,
    CatalogRequest,
    Garment,
    Match,
    Product,
    StyleRecommendation,
    StyleScore,
    User,
    UserProfile,
    UserRadarHistory,
)
from app.services.catalog_from_image import (
    CatalogConfig,
    _last_style_context,
    _search_serp,
    _style_recommendation_prompt,
    process_catalog_from_image,
)
from ml_core.embeddings import get_embedder
from ml_core.retrieval import CATEGORIES, get_catalog
from ml_core.taste import AXES, TasteProfileEngine, generate_aesthetic_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("poke-mcp")

mcp = FastMCP("Aesthetica — AI Fashion Intelligence")

DEMO_USER_ID: str | None = None

AXIS_LABELS = {
    "minimal_maximal": ("Minimal", "Maximal"),
    "structured_relaxed": ("Structured", "Relaxed"),
    "neutral_color_forward": ("Neutral", "Colorful"),
    "classic_experimental": ("Classic", "Experimental"),
    "casual_formal": ("Casual", "Formal"),
}

STYLE_AXES = ["casual", "minimal", "structured", "classic", "neutral"]


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


def _bar(value: float, width: int = 10) -> str:
    filled = round(value / 100 * width)
    return "█" * filled + "░" * (width - filled)


@mcp.tool()
def get_taste_profile() -> str:
    """Get your current fashion taste profile — a 5-axis radar showing your style DNA."""
    uid = _get_demo_user_id()
    if not uid:
        return "No user profile found. Upload an outfit first!"

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == uid).first()
        if not profile or not profile.radar_vector_json:
            return "No taste profile yet — upload an outfit to start building yours!"

        radar = profile.radar_vector_json
        captures_count = db.query(Capture).filter(
            Capture.user_id == uid, Capture.status == "done"
        ).count()

        lines = ["✦ Your Fashion Taste Profile ✦", ""]
        for axis, score in radar.items():
            lo, hi = AXIS_LABELS.get(axis, (axis, axis))
            lines.append(f"  {lo:<13} {_bar(score)} {hi:>13}  ({score:.0f}/100)")
        lines.append("")
        lines.append(f"Based on {captures_count} analyzed outfit(s).")

        if profile.brand_stats:
            top_brands = sorted(profile.brand_stats.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append(f"Top brands: {', '.join(b for b, _ in top_brands)}")

        if profile.color_stats:
            top_colors = sorted(profile.color_stats.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append(f"Favorite colors: {', '.join(c for c, _ in top_colors)}")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def get_recent_looks(limit: int = 5) -> str:
    """Browse your recently captured outfits."""
    uid = _get_demo_user_id()
    if not uid:
        return "No user found."

    db = SessionLocal()
    try:
        captures = (
            db.query(Capture)
            .filter(Capture.user_id == uid, Capture.status == "done")
            .order_by(desc(Capture.created_at))
            .limit(limit)
            .all()
        )
        if not captures:
            return "No outfits captured yet! Send me a photo to get started."

        lines = [f"Your {len(captures)} Most Recent Looks:", ""]
        for i, cap in enumerate(captures, 1):
            date = cap.created_at.strftime("%b %d, %Y") if cap.created_at else "Unknown"
            garment_count = len(cap.garments)
            match_count = len(cap.matches)
            attrs = cap.global_attributes_json or {}
            silhouette = attrs.get("silhouette", "")
            colors = attrs.get("colors", [])
            color_str = ", ".join(c.get("name", c.get("hex", "")) for c in colors[:2]) if colors else ""

            desc_parts = []
            if silhouette:
                desc_parts.append(silhouette)
            if color_str:
                desc_parts.append(color_str)
            desc_text = " — " + ", ".join(desc_parts) if desc_parts else ""

            lines.append(f"  {i}. [{date}] {garment_count} garment(s), {match_count} match(es){desc_text}")
            lines.append(f"     ID: {cap.id}")

        lines.append("")
        lines.append("Use get_look_details with an ID for more info on any look.")
        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def get_look_details(capture_id: str) -> str:
    """Get full details for a specific captured outfit including matched products."""
    uid = _get_demo_user_id()
    if not uid:
        return "No user found."

    db = SessionLocal()
    try:
        capture = (
            db.query(Capture)
            .filter(Capture.id == capture_id, Capture.user_id == uid)
            .first()
        )
        if not capture:
            return f"Look {capture_id} not found."

        lines = [f"Look Details — {capture.created_at.strftime('%b %d, %Y') if capture.created_at else ''}", ""]

        attrs = capture.global_attributes_json or {}
        if attrs.get("silhouette"):
            lines.append(f"Silhouette: {attrs['silhouette']}")
        colors = attrs.get("colors", [])
        if colors:
            lines.append(f"Colors: {', '.join(c.get('name', c.get('hex', '')) for c in colors[:4])}")

        if capture.garments:
            lines.append("")
            lines.append("Garments detected:")
            for g in capture.garments:
                g_attrs = g.attributes_json or {}
                color_info = ""
                g_colors = g_attrs.get("colors", [])
                if g_colors:
                    color_info = f" ({', '.join(c.get('name', c.get('hex', '')) for c in g_colors[:2])})"
                lines.append(f"  • {g.garment_type}{color_info}")

        if capture.matches:
            lines.append("")
            lines.append("Product matches:")
            for m in capture.matches[:5]:
                product = db.query(Product).filter(Product.id == m.product_id).first()
                if product:
                    price = f" — ${product.price:.0f}" if product.price else ""
                    lines.append(f"  {m.rank}. {product.title} by {product.brand}{price}")
                    lines.append(f"     Similarity: {m.similarity:.1%} | {product.product_url}")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def find_similar_products(query: str, category: str = "top", include_web: bool = False) -> str:
    """Search the fashion catalog for products matching a description. Set include_web=True to also search Google Shopping."""
    catalog = get_catalog()
    faiss_ready = catalog.is_ready()
    lines: list[str] = []

    if faiss_ready and category in CATEGORIES:
        embedding = get_embedder().text_embedding(query)
        results = catalog.query(category, embedding, top_k=5)

        if results:
            db = SessionLocal()
            try:
                lines.append(f"Catalog matches for \"{query}\" ({category}):")
                lines.append("")
                for r in results:
                    product = db.query(Product).filter(Product.id == r.product_id).first()
                    if product:
                        price = f" — ${product.price:.0f}" if product.price else ""
                        lines.append(f"  {r.rank}. {product.title} by {product.brand}{price}")
                        lines.append(f"     Match: {r.similarity:.1%} | {product.product_url}")
            finally:
                db.close()

    no_faiss_results = not lines

    if include_web or no_faiss_results:
        try:
            cfg = CatalogConfig()
            web_results = _search_serp(query, cfg, max_results=5)
            if web_results:
                if lines:
                    lines.append("")
                lines.append(f"Google Shopping results for \"{query}\":")
                lines.append("")
                for i, item in enumerate(web_results, 1):
                    price = f" — {item['price_text']}" if item.get("price_text") else ""
                    source = f" ({item['source']})" if item.get("source") else ""
                    lines.append(f"  {i}. {item['title']}{price}{source}")
                    lines.append(f"     {item['product_url']}")
        except Exception as exc:
            logger.warning("serp_search_failed: %s", exc)
            if no_faiss_results:
                lines.append(f"Web search failed: {exc}")

    if not lines:
        return f"No products found for '{query}'."

    return "\n".join(lines)


@mcp.tool()
def get_radar_history(days: int = 30) -> str:
    """See how your fashion taste has evolved over time."""
    uid = _get_demo_user_id()
    if not uid:
        return "No user found."

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        records = (
            db.query(UserRadarHistory)
            .filter(UserRadarHistory.user_id == uid, UserRadarHistory.created_at >= cutoff)
            .order_by(UserRadarHistory.created_at)
            .all()
        )
        if not records:
            return f"No taste history in the last {days} days."

        lines = [f"Taste Evolution — Last {days} Days ({len(records)} snapshots)", ""]

        first = records[0].radar_vector_json
        last = records[-1].radar_vector_json

        for axis in AXES:
            lo, hi = AXIS_LABELS.get(axis, (axis, axis))
            start_val = first.get(axis, 50)
            end_val = last.get(axis, 50)
            delta = end_val - start_val
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            lines.append(f"  {lo}/{hi}: {start_val:.0f} → {end_val:.0f} ({arrow}{abs(delta):.1f})")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def get_style_summary() -> str:
    """Get a natural language summary of your overall fashion identity."""
    uid = _get_demo_user_id()
    if not uid:
        return "No user found."

    db = SessionLocal()
    try:
        profile = db.query(UserProfile).filter(UserProfile.user_id == uid).first()
        if not profile or not profile.radar_vector_json:
            return "Not enough data for a style summary. Upload more outfits!"

        radar = profile.radar_vector_json

        captures_count = db.query(Capture).filter(
            Capture.user_id == uid, Capture.status == "done"
        ).count()

        last_capture = (
            db.query(Capture)
            .filter(Capture.user_id == uid, Capture.status == "done")
            .order_by(desc(Capture.created_at))
            .first()
        )

        lines = ["✦ Your Style Summary ✦", ""]

        if last_capture and last_capture.global_attributes_json:
            summary = generate_aesthetic_summary(last_capture.global_attributes_json, radar)
            lines.append(summary)
            lines.append("")

        dominant_traits = []
        for axis, score in radar.items():
            lo, hi = AXIS_LABELS.get(axis, (axis, axis))
            if score < 35:
                dominant_traits.append(lo.lower())
            elif score > 65:
                dominant_traits.append(hi.lower())
        if dominant_traits:
            lines.append(f"Strong style traits: {', '.join(dominant_traits)}")

        if profile.brand_stats:
            top_brands = sorted(profile.brand_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"Brand affinity: {', '.join(f'{b} ({c})' for b, c in top_brands)}")

        if profile.color_stats:
            top_colors = sorted(profile.color_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"Color palette: {', '.join(c for c, _ in top_colors)}")

        if profile.category_bias:
            top_cats = sorted(profile.category_bias.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append(f"Wardrobe focus: {', '.join(f'{c} ({n})' for c, n in top_cats)}")

        lines.append("")
        lines.append(f"Based on {captures_count} outfit(s) analyzed.")
        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def analyze_outfit(image_url: str) -> str:
    """Analyze an outfit image via URL — returns AI style scores across 5 axes, a description, and personalized product recommendations with rationale."""
    try:
        resp = httpx.get(image_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        image_bytes = resp.content
    except Exception as exc:
        return f"Failed to download image: {exc}"

    content_type = resp.headers.get("content-type", "image/jpeg")
    filename = image_url.rsplit("/", 1)[-1][:255] or "outfit.jpg"

    db = SessionLocal()
    try:
        result = process_catalog_from_image(db, image_bytes, filename, content_type)

        lines = ["✦ Outfit Analysis ✦", ""]

        if result.pipeline_status == "pipeline_error":
            return f"Analysis failed: {result.error or 'unknown error'}"

        if result.garment_name:
            garment_line = f"Detected: {result.garment_name}"
            if result.brand_hint:
                garment_line += f" (possibly {result.brand_hint})"
            lines.append(garment_line)

        # Fetch the style score that was just created for this request
        style_row = (
            db.query(StyleScore)
            .filter(StyleScore.request_id == result.request_id)
            .first()
        )
        if style_row:
            lines.append("")
            lines.append("Style Scores:")
            for axis in STYLE_AXES:
                score = getattr(style_row, axis, 50.0)
                lines.append(f"  {axis:<12} {_bar(score)} {score:.0f}/100")
            if style_row.description:
                lines.append("")
                lines.append(f"AI Description: {style_row.description}")

        # Fetch style recommendations (which have rationale)
        style_recs = (
            db.query(StyleRecommendation)
            .filter(StyleRecommendation.request_id == result.request_id)
            .order_by(StyleRecommendation.rank)
            .all()
        )
        if style_recs:
            if style_recs[0].rationale:
                lines.append("")
                lines.append(f"Why these picks: {style_recs[0].rationale}")
            lines.append("")
            lines.append("Recommended Products:")
            for rec in style_recs:
                price = f" — {rec.price_text}" if rec.price_text else ""
                source = f" ({rec.source})" if rec.source else ""
                lines.append(f"  {rec.rank}. {rec.title}{price}{source}")
                lines.append(f"     {rec.product_url}")
        elif result.recommendations:
            lines.append("")
            lines.append("Recommended Products:")
            for rec in result.recommendations:
                price = f" — {rec.price_text}" if rec.price_text else ""
                source = f" ({rec.source})" if rec.source else ""
                lines.append(f"  {rec.rank}. {rec.title}{price}{source}")
                lines.append(f"     {rec.product_url}")

        return "\n".join(lines)
    except Exception as exc:
        logger.exception("analyze_outfit_failed")
        return f"Analysis failed: {type(exc).__name__}: {exc}"
    finally:
        db.close()


@mcp.tool()
def get_style_scores(limit: int = 5) -> str:
    """Browse your style score history — the AI's analysis of each captured image across 5 style axes."""
    db = SessionLocal()
    try:
        rows = (
            db.query(StyleScore)
            .order_by(desc(StyleScore.created_at))
            .limit(max(1, min(limit, 20)))
            .all()
        )
        if not rows:
            return "No style scores yet. Analyze an outfit to start building your style profile!"

        lines = [f"✦ Style Score History ({len(rows)} entries) ✦", ""]

        for i, row in enumerate(rows, 1):
            date = row.created_at.strftime("%b %d, %Y %H:%M") if row.created_at else "Unknown"
            lines.append(f"{i}. [{date}]")
            if row.description:
                lines.append(f"   {row.description[:200]}")
            for axis in STYLE_AXES:
                score = getattr(row, axis, 50.0)
                lines.append(f"   {axis:<12} {_bar(score)} {score:.0f}")
            lines.append("")

        # Show trend if we have at least 2 entries
        if len(rows) >= 2:
            latest = rows[0]
            oldest = rows[-1]
            lines.append("Trend (latest vs oldest):")
            for axis in STYLE_AXES:
                new_val = getattr(latest, axis, 50.0)
                old_val = getattr(oldest, axis, 50.0)
                delta = new_val - old_val
                arrow = "↑" if delta > 2 else "↓" if delta < -2 else "→"
                lines.append(f"  {axis:<12} {old_val:.0f} → {new_val:.0f} {arrow}")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def get_catalog_results(limit: int = 5) -> str:
    """Browse past catalog analyses with product recommendations and AI rationale."""
    db = SessionLocal()
    try:
        requests = (
            db.query(CatalogRequest)
            .filter(CatalogRequest.pipeline_status != "processing")
            .order_by(desc(CatalogRequest.created_at))
            .limit(max(1, min(limit, 20)))
            .all()
        )
        if not requests:
            return "No catalog analyses yet. Use analyze_outfit to scan an image!"

        lines = [f"✦ Catalog Results ({len(requests)} entries) ✦", ""]

        for i, req in enumerate(requests, 1):
            date = req.created_at.strftime("%b %d, %Y %H:%M") if req.created_at else "Unknown"
            garment = req.garment_name or "unknown"
            brand = f" ({req.brand_hint})" if req.brand_hint else ""
            status = req.pipeline_status
            lines.append(f"{i}. [{date}] {garment}{brand} — {status}")

            # Style scores for this request
            style_row = (
                db.query(StyleScore)
                .filter(StyleScore.request_id == req.id)
                .first()
            )
            if style_row:
                scores = " | ".join(
                    f"{a}: {getattr(style_row, a, 50):.0f}" for a in STYLE_AXES
                )
                lines.append(f"   Scores: {scores}")

            # Style recommendations (with rationale)
            style_recs = (
                db.query(StyleRecommendation)
                .filter(StyleRecommendation.request_id == req.id)
                .order_by(StyleRecommendation.rank)
                .all()
            )
            if style_recs:
                if style_recs[0].rationale:
                    lines.append(f"   Rationale: {style_recs[0].rationale[:200]}")
                for rec in style_recs[:3]:
                    price = f" — {rec.price_text}" if rec.price_text else ""
                    source = f" ({rec.source})" if rec.source else ""
                    lines.append(f"   • {rec.title}{price}{source}")
                    lines.append(f"     {rec.product_url}")
            elif req.recommendations:
                for rec in req.recommendations[:3]:
                    price = f" — {rec.price_text}" if rec.price_text else ""
                    source = f" ({rec.source})" if rec.source else ""
                    lines.append(f"   • {rec.title}{price}{source}")
                    lines.append(f"     {rec.product_url}")

            lines.append("")

        return "\n".join(lines)
    finally:
        db.close()


@mcp.tool()
def get_style_recommendations(category_hint: str = "") -> str:
    """Get AI-powered product recommendations based on your rolling style profile. Optionally filter by category (e.g. 'denim jacket', 'sneakers')."""
    db = SessionLocal()
    try:
        cfg = CatalogConfig()
        style_ctx = _last_style_context(db, limit=5)

        if not style_ctx.get("descriptions"):
            return "No style history yet. Analyze some outfits first to build your profile!"

        if category_hint:
            style_ctx["category_hint"] = category_hint

        reco_ctx = _style_recommendation_prompt(style_ctx, cfg)
        search_query = reco_ctx.get("search_query", "")
        rationale = reco_ctx.get("rationale", "")

        if category_hint and category_hint.lower() not in search_query.lower():
            search_query = f"{category_hint} {search_query}"

        web_results = _search_serp(search_query, cfg, max_results=5)

        lines = ["✦ Style-Based Recommendations ✦", ""]

        # Show the rolling profile
        avg = style_ctx.get("avg", {})
        lines.append("Your rolling style profile:")
        for axis in STYLE_AXES:
            score = avg.get(axis, 50.0)
            lines.append(f"  {axis:<12} {_bar(score)} {score:.0f}")

        if rationale:
            lines.append("")
            lines.append(f"AI Rationale: {rationale}")

        lines.append("")
        lines.append(f"Search: \"{search_query}\"")
        lines.append("")

        if web_results:
            lines.append("Recommended Products:")
            for i, item in enumerate(web_results, 1):
                price = f" — {item['price_text']}" if item.get("price_text") else ""
                source = f" ({item['source']})" if item.get("source") else ""
                lines.append(f"  {i}. {item['title']}{price}{source}")
                lines.append(f"     {item['product_url']}")
        else:
            lines.append("No products found for this query.")

        return "\n".join(lines)
    except Exception as exc:
        logger.exception("style_recommendations_failed")
        return f"Failed to generate recommendations: {type(exc).__name__}: {exc}"
    finally:
        db.close()


@mcp.tool()
def get_wardrobe_stats() -> str:
    """Get aggregate wardrobe statistics — total captures, catalog scans, average style scores, top brands and colors."""
    uid = _get_demo_user_id()
    db = SessionLocal()
    try:
        lines = ["✦ Wardrobe Stats ✦", ""]

        # Capture stats (user-scoped if available)
        if uid:
            capture_count = db.query(Capture).filter(
                Capture.user_id == uid, Capture.status == "done"
            ).count()
            last_capture = (
                db.query(Capture)
                .filter(Capture.user_id == uid, Capture.status == "done")
                .order_by(desc(Capture.created_at))
                .first()
            )
        else:
            capture_count = 0
            last_capture = None

        catalog_count = db.query(CatalogRequest).filter(
            CatalogRequest.pipeline_status != "processing"
        ).count()
        style_score_count = db.query(StyleScore).count()

        lines.append(f"Total outfit captures: {capture_count}")
        lines.append(f"Catalog scans: {catalog_count}")
        lines.append(f"Style scores recorded: {style_score_count}")

        if last_capture and last_capture.created_at:
            lines.append(f"Last capture: {last_capture.created_at.strftime('%b %d, %Y %H:%M')}")

        # Average style scores
        if style_score_count > 0:
            avgs = db.query(
                func.avg(StyleScore.casual),
                func.avg(StyleScore.minimal),
                func.avg(StyleScore.structured),
                func.avg(StyleScore.classic),
                func.avg(StyleScore.neutral),
            ).one()
            avg_map = dict(zip(STYLE_AXES, avgs))
            lines.append("")
            lines.append("Average Style Scores:")
            for axis in STYLE_AXES:
                val = float(avg_map.get(axis) or 50.0)
                lines.append(f"  {axis:<12} {_bar(val)} {val:.0f}")

        # User profile stats
        if uid:
            profile = db.query(UserProfile).filter(UserProfile.user_id == uid).first()
            if profile:
                if profile.brand_stats:
                    top_brands = sorted(profile.brand_stats.items(), key=lambda x: x[1], reverse=True)[:5]
                    lines.append("")
                    lines.append(f"Top brands: {', '.join(f'{b} ({c})' for b, c in top_brands)}")
                if profile.color_stats:
                    top_colors = sorted(profile.color_stats.items(), key=lambda x: x[1], reverse=True)[:5]
                    lines.append(f"Top colors: {', '.join(c for c, _ in top_colors)}")

        return "\n".join(lines)
    finally:
        db.close()


if __name__ == "__main__":
    _get_demo_user_id()
    get_catalog()
    logger.info("starting Aesthetica MCP server on port 8787")
    mcp.run(transport="sse", host="0.0.0.0", port=8787)
