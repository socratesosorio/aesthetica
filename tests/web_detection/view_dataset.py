#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _collect_images(root: Path) -> list[Path]:
    return sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS],
        key=lambda p: p.name.lower(),
    )


def _collect_images_recursive(root: Path) -> list[Path]:
    return sorted(
        [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS],
        key=lambda p: str(p).lower(),
    )


def _html_for(images: list[Path]) -> str:
    rel = [str(p.as_posix()) for p in images]
    names = [str(p) for p in images]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dataset Viewer</title>
  <style>
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background: linear-gradient(140deg, #f0ecdf, #e8f0ee);
      color: #1f1f1f;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 18px; }}
    .stage {{
      position: relative;
      border: 1px solid #d4d1c6;
      border-radius: 14px;
      background: #fffdf8;
      min-height: 74vh;
      display: grid;
      place-items: center;
      overflow: hidden;
    }}
    img {{
      max-width: 100%;
      max-height: 74vh;
      object-fit: contain;
      display: block;
    }}
    .btn {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      width: 54px;
      height: 54px;
      border: 0;
      border-radius: 999px;
      background: rgba(20, 38, 42, 0.8);
      color: #fff;
      font-size: 30px;
      cursor: pointer;
    }}
    #prev {{ left: 12px; }}
    #next {{ right: 12px; }}
    .meta {{
      margin-top: 10px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 15px;
      color: #38352f;
    }}
    .hint {{ color: #6a665d; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="stage">
      <button id="prev" class="btn" aria-label="Previous image">&#8249;</button>
      <img id="viewer" alt="dataset-image" />
      <button id="next" class="btn" aria-label="Next image">&#8250;</button>
    </div>
    <div class="meta">
      <div id="name"></div>
      <div id="count"></div>
    </div>
    <p class="hint">Use left/right arrows on keyboard or click the buttons.</p>
  </div>
  <script>
    const srcs = {json.dumps(rel)};
    const names = {json.dumps(names)};
    let i = 0;
    const img = document.getElementById("viewer");
    const name = document.getElementById("name");
    const count = document.getElementById("count");

    function render() {{
      img.src = srcs[i];
      name.textContent = names[i];
      count.textContent = `${{i + 1}} / ${{srcs.length}}`;
    }}
    function next() {{
      i = (i + 1) % srcs.length;
      render();
    }}
    function prev() {{
      i = (i - 1 + srcs.length) % srcs.length;
      render();
    }}
    document.getElementById("next").addEventListener("click", next);
    document.getElementById("prev").addEventListener("click", prev);
    document.addEventListener("keydown", (e) => {{
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft") prev();
    }});
    render();
  </script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an arrow-key dataset image viewer HTML.")
    parser.add_argument(
        "--dir",
        default="tests/web_detection/test_images",
        help="Directory containing images to view",
    )
    parser.add_argument(
        "--out",
        default="tests/web_detection/_reports/dataset_viewer.html",
        help="HTML output path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of images to include (0 means all)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search for images recursively under --dir",
    )
    args = parser.parse_args()

    image_dir = Path(args.dir)
    if not image_dir.exists() or not image_dir.is_dir():
        print(f"Invalid image directory: {image_dir}")
        return 1

    images = _collect_images_recursive(image_dir) if args.recursive else _collect_images(image_dir)
    if not images and not args.recursive:
        # Helpful fallback when user points to a parent folder.
        images = _collect_images_recursive(image_dir)
    if not images:
        print(f"No images found in: {image_dir}")
        return 1
    if args.limit < 0:
        print("--limit must be >= 0")
        return 1
    if args.limit > 0:
        images = images[: args.limit]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    page = _html_for(images)
    out.write_text(page, encoding="utf-8")
    print(f"viewer={out}")
    print(f"images={len(images)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
