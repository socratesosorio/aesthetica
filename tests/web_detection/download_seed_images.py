#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


def _safe_name(index: int, url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    tail = parsed.path.strip("/").split("/")[-2:]  # photos/{id}
    slug = "_".join(tail) if tail else f"img_{index:03d}"
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug).strip("_") or f"img_{index:03d}"

    ext = ".jpg"
    if content_type:
        ct = content_type.lower()
        if "png" in ct:
            ext = ".png"
        elif "webp" in ct:
            ext = ".webp"
    return f"{index:03d}_{slug}{ext}"


def _download_one(session: requests.Session, url: str, out_dir: Path, index: int, timeout: int) -> Path:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    name = _safe_name(index, url, resp.headers.get("Content-Type"))
    out_path = out_dir / name
    out_path.write_bytes(resp.content)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Download seed shirt images from a URL list")
    parser.add_argument(
        "--urls-file",
        default="tests/web_detection/seed_shirt_urls.txt",
        help="Text file with one image URL per line",
    )
    parser.add_argument(
        "--out-dir",
        default="tests/web_detection/test_images/seed30",
        help="Directory to write downloaded images",
    )
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    args = parser.parse_args()

    urls_file = Path(args.urls_file)
    if not urls_file.exists():
        print(f"Missing URL file: {urls_file}")
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = [line.strip() for line in urls_file.read_text().splitlines() if line.strip() and not line.strip().startswith("#")]
    if not urls:
        print("No URLs found.")
        return 1

    session = requests.Session()
    ok = 0
    failed = 0
    for i, url in enumerate(urls, start=1):
        try:
            p = _download_one(session, url, out_dir, i, args.timeout)
            ok += 1
            print(f"[OK] {url} -> {p}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {url} ({type(exc).__name__}: {exc})")

    print(f"\nDone: downloaded={ok} failed={failed} out_dir={out_dir}")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
