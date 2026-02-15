#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "services" / "ml"))

from ml_core.segment_and_detect import SegmentAndCatalogPipeline
from ml_core.shirt_catalog import OpenAIQuotaExceededError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
STOPWORDS = {
    "image",
    "img",
    "photo",
    "picture",
    "capture",
    "look",
    "outfit",
    "test",
    "sample",
}


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _expected_terms(stem: str) -> list[str]:
    base = [t for t in re.findall(r"[a-z0-9]+", stem.lower()) if len(t) >= 3 and t not in STOPWORDS]
    out: list[str] = []
    for t in base:
        out.append(t)
        if t.endswith("s") and len(t) > 4:
            out.append(t[:-1])
        else:
            out.append(t + "s")
    # de-dupe keep order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped or [stem.lower()]


def _top5_related(stem: str, result) -> tuple[bool, str]:
    expected = _expected_terms(stem)
    hay = " ".join(
        _norm((m.title or "") + " " + (m.product_url or ""))
        for m in result.catalog.matches[:5]
    )
    for term in expected:
        if term in hay:
            return True, term
    return False, expected[0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run shirt catalog pipeline against all images in a folder and print links/results. "
            "Use --assert-related if you also want filename-token pass/fail checks."
        )
    )
    parser.add_argument("--dir", default="tests/web_detection/test_images", help="Image directory")
    parser.add_argument("--garment", default="top", help="Garment type")
    parser.add_argument("--rich-context", action="store_true", help="Use extra exact-item context from ChatGPT in query generation")
    parser.add_argument("--sleep-between-images", type=float, default=3.0, help="Seconds to sleep between images")
    parser.add_argument(
        "--assert-related",
        action="store_true",
        help="Assert that top-5 results contain tokens related to each image filename",
    )
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"Missing directory: {root}")
        return 1

    images = sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
    if not images:
        print("No images found.")
        return 1

    pipeline = SegmentAndCatalogPipeline()
    failed: list[str] = []

    print("\n" + "=" * 70)
    print("  Batch Catalog Run")
    print("=" * 70)

    for p in images:
        stem = p.stem
        print(f"\n--- {p.name} ---")
        try:
            result = pipeline.run(
                str(p),
                garment_type=args.garment,
                top_k=5,
                use_rich_context=args.rich_context,
            )
        except OpenAIQuotaExceededError as exc:
            print(f"PAUSED: {exc}")
            print("Please add OpenAI credits / swap key, then rerun this command.")
            return 2
        except Exception as exc:
            print(f"FAIL: pipeline error: {type(exc).__name__}: {exc}")
            failed.append(p.name)
            continue

        print(
            f"status={result.catalog.status} garment={result.catalog.signal.garment_name} "
            f"brand_hint={result.catalog.signal.brand_hint} exact_item_hint={result.catalog.signal.exact_item_hint}"
        )
        for i, m in enumerate(result.catalog.matches[:5]):
            print(f"  [{i}] {m.title} | {m.price_text or '(no price)'} | {m.product_url}")

        if args.assert_related:
            ok, matched = _top5_related(stem, result)
            if not ok:
                print(f"FAIL: top-5 not related to filename tokens for '{stem}'")
                failed.append(p.name)
            else:
                print(f"PASS: related token matched: {matched}")

        if args.sleep_between_images > 0:
            time.sleep(args.sleep_between_images)

    print("\n" + "=" * 70)
    if args.assert_related and failed:
        print(f"FAILED {len(failed)} image(s): {', '.join(failed)}")
        return 1
    if args.assert_related:
        print(f"PASS: all {len(images)} image(s) returned related top-5 results")
    else:
        print(f"DONE: processed {len(images)} image(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
