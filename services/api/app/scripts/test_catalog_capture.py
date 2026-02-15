#!/usr/bin/env python3
"""Test the catalog-from-image endpoint the same way the Flutter capture screen does.

Usage:
    # With a local image file:
    python test_catalog_capture.py --image path/to/outfit.jpg

    # With a URL (downloads first):
    python test_catalog_capture.py --url "https://example.com/hoodie.jpg"

    # With no args — uses a sample image from the web:
    python test_catalog_capture.py
"""
from __future__ import annotations

import argparse
import sys

import httpx
from dotenv import load_dotenv


SAMPLE_IMAGE_URL = "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=600"

DEFAULT_API_BASE = "http://localhost:8001"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a test image to the catalog API.")
    parser.add_argument("--image", default=None, help="Path to a local JPEG/PNG image file.")
    parser.add_argument("--url", default=None, help="URL of an image to download and send.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Catalog API base URL.")
    return parser.parse_args()


def load_image(path: str | None, url: str | None) -> bytes:
    if path:
        print(f"Loading image from file: {path}")
        with open(path, "rb") as f:
            return f.read()

    image_url = url or SAMPLE_IMAGE_URL
    print(f"Downloading image: {image_url}")
    resp = httpx.get(image_url, timeout=15, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def main() -> int:
    load_dotenv()
    args = parse_args()

    image_bytes = load_image(args.image, args.url)
    print(f"Image size: {len(image_bytes):,} bytes")

    # Send as raw JPEG body — same as the Flutter app does
    endpoint = f"{args.api_base}/v1/catalog/from-image"
    print(f"POST {endpoint}")

    try:
        resp = httpx.post(
            endpoint,
            headers={"Content-Type": "image/jpeg"},
            content=image_bytes,
            timeout=60,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(f"error: API returned {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: request failed: {exc}", file=sys.stderr)
        return 1

    data = resp.json()
    print(f"\nStatus: {data.get('pipeline_status')}")
    print(f"Garment: {data.get('garment_name')}")
    print(f"Brand: {data.get('brand_hint')}")
    print(f"Confidence: {data.get('confidence')}")

    recs = data.get("recommendations", [])
    if recs:
        print(f"\n{len(recs)} recommendation(s):")
        for r in recs:
            price = f" — {r['price_text']}" if r.get("price_text") else ""
            source = f" ({r['source']})" if r.get("source") else ""
            print(f"  {r['rank']}. {r['title']}{price}{source}")
            print(f"     {r['product_url']}")
    else:
        print(f"\nNo recommendations. Error: {data.get('error')}")

    print("\n(If POKE_API_KEY is set, a Poke message was also sent.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
