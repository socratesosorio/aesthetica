#!/usr/bin/env python3
from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from app.services.catalog_from_image import CatalogConfig, _lens_to_shopping_context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the Lens -> Shopping path used for Poke context.")
    parser.add_argument("--image", required=True, help="Path to local image file.")
    parser.add_argument("--api-base", default="http://localhost:8001", help="Catalog API base URL.")
    parser.add_argument("--bucket", default=None, help="Supabase bucket name (default: env SUPABASE_STORAGE_BUCKET or captures).")
    return parser.parse_args()


def _content_type_for(path: Path) -> str:
    guess, _ = mimetypes.guess_type(str(path))
    return guess or "image/jpeg"


def _ext_for(path: Path, content_type: str) -> str:
    if content_type == "image/png":
        return "png"
    if content_type in {"image/jpeg", "image/jpg"}:
        return "jpg"
    if path.suffix:
        return path.suffix.lstrip(".").lower()
    return "jpg"


def main() -> int:
    load_dotenv()
    args = parse_args()

    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        print(f"error: image does not exist: {image_path}", file=sys.stderr)
        return 2

    content_type = _content_type_for(image_path)
    with image_path.open("rb") as f:
        files = {"image": (image_path.name, f, content_type)}
        endpoint = f"{args.api_base.rstrip('/')}/v1/catalog/from-image"
        print(f"POST {endpoint}")
        try:
            resp = httpx.post(endpoint, files=files, timeout=180)
            resp.raise_for_status()
        except Exception as exc:
            print(f"error: API request failed: {exc}", file=sys.stderr)
            return 1

    payload = resp.json()
    request_id = payload.get("request_id")
    print(f"request_id: {request_id}")
    print(f"pipeline_status: {payload.get('pipeline_status')}")
    print(f"api_error: {payload.get('error')}")
    if not request_id:
        print("error: missing request_id in response", file=sys.stderr)
        return 1

    supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    bucket = (args.bucket or os.getenv("SUPABASE_STORAGE_BUCKET") or "captures").strip()
    if not supabase_url:
        print("error: SUPABASE_URL not set; cannot verify lens image URL", file=sys.stderr)
        return 2

    ext = _ext_for(image_path, content_type)
    image_url = f"{supabase_url}/storage/v1/object/public/{bucket}/catalog-inputs/{request_id}.{ext}"
    try:
        status = httpx.get(image_url, timeout=20).status_code
    except Exception as exc:
        print(f"error: capture URL check failed: {exc}", file=sys.stderr)
        return 1
    print(f"capture_blob_status: {status}")
    print(f"capture_blob_url: {image_url}")

    cfg = CatalogConfig()
    ctx = _lens_to_shopping_context(image_url, cfg)
    desc = ctx.get("description")
    shopping = ctx.get("shopping") or []
    print("\nLens -> Shopping context:")
    print(f"normalized_description: {desc}")
    print(f"shopping_count: {len(shopping)}")
    for idx, row in enumerate(shopping[:5], start=1):
        title = row.get("title")
        price = row.get("price_text")
        source = row.get("source")
        link = row.get("product_url")
        print(f"{idx}. {title} | {price} | {source}")
        print(f"   {link}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
