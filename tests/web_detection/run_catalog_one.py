#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "services" / "ml"))

from ml_core.segment_and_detect import SegmentAndCatalogPipeline
from ml_core.shirt_catalog import OpenAIQuotaExceededError


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenAI->Serp catalog pipeline for one image")
    parser.add_argument("image", help="Path or URL to image")
    parser.add_argument("--garment", default="top", help="Garment type")
    parser.add_argument("--top-k", type=int, default=5, help="Top matches")
    parser.add_argument("--rich-context", action="store_true", help="Use extra exact-item context from ChatGPT in query generation")
    parser.add_argument("--expect", default=None, help="Optional expected token (e.g. essentials, dodgers)")
    args = parser.parse_args()

    image_input: str | Image.Image
    display_name = args.image
    if args.image.startswith("http://") or args.image.startswith("https://"):
        try:
            resp = requests.get(args.image, timeout=30)
            resp.raise_for_status()
            from io import BytesIO

            image_input = Image.open(BytesIO(resp.content)).convert("RGB")
        except Exception as exc:
            print(f"Failed to download image URL: {exc}")
            return 1
    else:
        p = Path(args.image)
        if not p.exists():
            print(f"Missing image: {p}")
            return 1
        image_input = str(p)
        display_name = p.name

    pipeline = SegmentAndCatalogPipeline()
    try:
        result = pipeline.run(
            image_input,
            garment_type=args.garment,
            top_k=args.top_k,
            use_rich_context=args.rich_context,
        )
    except OpenAIQuotaExceededError as exc:
        print(f"PAUSED: {exc}")
        return 2

    print("\n" + "=" * 70)
    print(f"  {display_name}")
    print("=" * 70)
    print(f"status={result.catalog.status}")
    print(f"garment={result.catalog.signal.garment_name}")
    print(f"brand_hint={result.catalog.signal.brand_hint}")
    print(f"exact_item_hint={result.catalog.signal.exact_item_hint}")
    print(f"confidence={result.catalog.signal.confidence:.2f}")
    print("queries=")
    for q in result.catalog.queries:
        print(f"  - {q}")

    print("matches=")
    for i, m in enumerate(result.catalog.matches[: args.top_k]):
        print(f"  [{i}] {m.title} | {m.price_text or '(no price)'} | {m.product_url}")

    if args.expect:
        token = args.expect.lower().strip()
        hay = " ".join(
            re.sub(r"[^a-z0-9]+", " ", (m.title + " " + m.product_url).lower())
            for m in result.catalog.matches[: args.top_k]
        )
        if token in hay:
            print(f"\nEXPECT CHECK: PASS ({args.expect})")
        else:
            print(f"\nEXPECT CHECK: FAIL ({args.expect}) not found in top-{args.top_k}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
