from __future__ import annotations

import logging
import uuid
from collections import Counter
from io import BytesIO

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import capture_id_ctx
from app.models import Capture, Garment, Match, Product, UserProfile, UserRadarHistory
from app.services.notifier import PokeNotifier
from ml_core.config import CONFIG
from ml_core.pipeline import CapturePipeline
from ml_core.retrieval import SearchResult, get_catalog
from ml_core.storage import get_storage
from ml_core.taste import TasteProfileEngine, generate_aesthetic_summary
from ml_core.utils import b64_to_ndarray, blur_faces_safety, l2_normalize, ndarray_to_b64

logger = logging.getLogger(__name__)


def _bytes_to_vec(payload: bytes | None) -> np.ndarray | None:
    if not payload:
        return None
    return np.frombuffer(payload, dtype=np.float32)


def _vec_to_bytes(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


def _pick_price_tiers(products: list[Product], ranked: list[SearchResult]) -> list[tuple[Product, SearchResult, str]]:
    if not ranked:
        return []

    p_map = {p.id: p for p in products}
    closest = next((r for r in ranked if r.product_id in p_map), None)
    if closest is None:
        return []

    out: list[tuple[Product, SearchResult, str]] = []
    base_product = p_map[closest.product_id]
    out.append((base_product, closest, "closest"))

    if base_product.price is None:
        return out

    lower = None
    premium = None
    for r in ranked:
        p = p_map.get(r.product_id)
        if p is None or p.price is None or p.id == base_product.id:
            continue
        if lower is None and p.price <= base_product.price * 0.8:
            lower = (p, r, "lower")
        if premium is None and p.price >= base_product.price * 1.2:
            premium = (p, r, "premium")
        if lower and premium:
            break

    if lower:
        out.append(lower)
    if premium:
        out.append(premium)
    return out


def _format_delta(delta: dict[str, float]) -> str:
    label_map = {
        "minimal_maximal": "Minimal/Maximal",
        "structured_relaxed": "Structured/Relaxed",
        "neutral_color_forward": "Neutral/Color",
        "classic_experimental": "Classic/Experimental",
        "casual_formal": "Casual/Formal",
    }
    chunks = []
    for k, v in delta.items():
        sign = "+" if v >= 0 else ""
        chunks.append(f"{sign}{v:.0f} {label_map.get(k, k)}")
    return ", ".join(chunks)


def _merge_color_stats(old: dict, attrs: dict) -> dict:
    acc = Counter(old or {})
    for c in attrs.get("colors", []):
        hex_code = c.get("hex")
        pct = float(c.get("pct", 0.0))
        if hex_code:
            acc[hex_code] += pct
    total = sum(acc.values()) or 1.0
    return {k: round(v / total, 4) for k, v in acc.items()}


def process_capture(db: Session, capture_id: str, notifier: PokeNotifier | None = None) -> None:
    token = capture_id_ctx.set(capture_id)
    notifier = notifier or PokeNotifier()
    notification_payload: tuple[dict, dict[str, float], dict[str, float]] | None = None

    try:
        try:
            capture = db.query(Capture).filter(Capture.id == capture_id).first()
            if capture is None:
                logger.error("capture_not_found")
                return

            if capture.status == "done":
                logger.info("capture_already_processed")
                return

            capture.status = "processing"
            capture.error = None
            db.commit()

            storage = get_storage()
            image_bytes = storage.read_bytes(capture.image_path)
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            image = blur_faces_safety(image)

            pipeline = CapturePipeline(catalog=get_catalog())
            result = pipeline.run(image)

            capture.global_embedding = _vec_to_bytes(result.global_embedding)
            capture.global_attributes_json = result.global_attributes

            created_garments: list[Garment] = []

            for g in result.garments:
                buf = BytesIO()
                g.crop.save(buf, format="PNG")
                crop_key = f"garments/{capture.user_id}/{capture.id}/{g.garment_type}_{uuid.uuid4().hex[:8]}.png"
                crop_path = storage.put_bytes(crop_key, buf.getvalue(), content_type="image/png")

                garment = Garment(
                    capture_id=capture.id,
                    garment_type=g.garment_type,
                    crop_path=crop_path,
                    embedding_vector=_vec_to_bytes(g.embedding),
                    attributes_json=g.attributes,
                )
                db.add(garment)
                db.flush()
                created_garments.append(garment)

                ranked = get_catalog().query(g.garment_type, g.embedding, top_k=settings.default_top_k)
                pids = [r.product_id for r in ranked]
                products = db.query(Product).filter(Product.id.in_(pids)).all() if pids else []
                tiered = _pick_price_tiers(products, ranked)

                for product, rank_meta, group in tiered:
                    db.add(
                        Match(
                            capture_id=capture.id,
                            garment_id=garment.id,
                            product_id=product.id,
                            rank=rank_meta.rank,
                            similarity=rank_meta.similarity,
                            match_group=group,
                        )
                    )

            if not created_garments:
                ranked = get_catalog().query("top", result.global_embedding, top_k=settings.default_top_k)
                pids = [r.product_id for r in ranked]
                products = db.query(Product).filter(Product.id.in_(pids)).all() if pids else []
                tiered = _pick_price_tiers(products, ranked)
                for product, rank_meta, group in tiered:
                    db.add(
                        Match(
                            capture_id=capture.id,
                            garment_id=None,
                            product_id=product.id,
                            rank=rank_meta.rank,
                            similarity=rank_meta.similarity,
                            match_group=group,
                        )
                    )

            profile = db.query(UserProfile).filter(UserProfile.user_id == capture.user_id).first()
            if profile is None:
                profile = UserProfile(
                    user_id=capture.user_id,
                    radar_vector_json={},
                    brand_stats={},
                    color_stats={},
                    category_bias={},
                )
                db.add(profile)
                db.flush()

            taste = TasteProfileEngine()
            prev_embedding = _bytes_to_vec(profile.embedding_vector)
            prev_radar = profile.radar_vector_json or {}

            updated_embedding = taste.update_embedding(prev_embedding, result.global_embedding)
            updated_radar = taste.radar_scores(updated_embedding)
            delta = taste.delta(prev_radar, updated_radar)

            profile.embedding_vector = _vec_to_bytes(updated_embedding)
            profile.radar_vector_json = updated_radar

            brand_counts = Counter(profile.brand_stats or {})
            for m in db.query(Match).filter(Match.capture_id == capture.id).all():
                product = db.query(Product).filter(Product.id == m.product_id).first()
                if product:
                    brand_counts[product.brand] += 1
            profile.brand_stats = dict(brand_counts)

            color_stats = profile.color_stats or {}
            for g in created_garments:
                color_stats = _merge_color_stats(color_stats, g.attributes_json)
            profile.color_stats = color_stats

            cat_counts = Counter(profile.category_bias or {})
            for g in created_garments:
                cat_counts[g.garment_type] += 1
            profile.category_bias = dict(cat_counts)

            db.add(
                UserRadarHistory(
                    user_id=capture.user_id,
                    radar_vector_json=updated_radar,
                )
            )

            capture.status = "done"
            capture.error = None
            db.commit()
            notification_payload = (result.global_attributes, updated_radar, delta)
        except Exception as exc:
            logger.exception("capture_processing_failed")
            db.rollback()
            cap = db.query(Capture).filter(Capture.id == capture_id).first()
            if cap and cap.status != "done":
                cap.status = "failed"
                cap.error = str(exc)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("capture_mark_failed_commit_error")
            raise

        if notification_payload is not None:
            attrs, radar, delta = notification_payload
            try:
                top_matches = (
                    db.query(Match, Product)
                    .join(Product, Product.id == Match.product_id)
                    .filter(Match.capture_id == capture_id)
                    .order_by(Match.rank.asc())
                    .limit(5)
                    .all()
                )

                summary = generate_aesthetic_summary(attrs, radar)
                delta_line = _format_delta(delta)
                links = [f"{p.title} {p.product_url}" for _, p in top_matches]

                message = (
                    f"{summary}\n"
                    f"Radar delta: {delta_line}\n"
                    f"Top matches: {' | '.join(links)}\n"
                    f"View: {settings.base_dashboard_url}/looks/{capture_id}"
                )
                notifier.send(message)
            except Exception:
                logger.exception("capture_notify_failed")
    finally:
        capture_id_ctx.reset(token)
