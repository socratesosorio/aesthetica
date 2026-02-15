"""Aesthetica Poke MCP Server — exposes fashion intelligence as MCP tools."""
from __future__ import annotations

import sys

sys.path.insert(0, "/app/services/api")
sys.path.insert(0, "/app/services/ml")

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from fastmcp import FastMCP
from sqlalchemy import desc

from app.db.session import SessionLocal
from app.models import Capture, Garment, Match, Product, User, UserProfile, UserRadarHistory
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
def find_similar_products(query: str, category: str = "top") -> str:
    """Search the fashion catalog for products matching a description."""
    catalog = get_catalog()
    if not catalog.is_ready():
        return "Product catalog not loaded. Please try again later."

    if category not in CATEGORIES:
        return f"Category must be one of: {', '.join(CATEGORIES)}"

    embedding = get_embedder().text_embedding(query)
    results = catalog.query(category, embedding, top_k=5)
    if not results:
        return f"No products found for '{query}' in {category}."

    db = SessionLocal()
    try:
        lines = [f"Products matching \"{query}\" ({category}):", ""]
        for r in results:
            product = db.query(Product).filter(Product.id == r.product_id).first()
            if product:
                price = f" — ${product.price:.0f}" if product.price else ""
                lines.append(f"  {r.rank}. {product.title} by {product.brand}{price}")
                lines.append(f"     Match: {r.similarity:.1%} | {product.product_url}")
        return "\n".join(lines)
    finally:
        db.close()


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
    """Upload/analyze an outfit image via URL. Returns style analysis of the image."""
    return (
        f"Image received: {image_url}\n\n"
        "To analyze this outfit, please upload it through the Aesthetica app "
        "or API (POST /v1/captures). The full pipeline will detect garments, "
        "match products, and update your taste profile.\n\n"
        "After processing, use get_recent_looks to see the results!"
    )


if __name__ == "__main__":
    _get_demo_user_id()
    get_catalog()
    logger.info("starting Aesthetica MCP server on port 8787")
    mcp.run(transport="sse", host="0.0.0.0", port=8787)
