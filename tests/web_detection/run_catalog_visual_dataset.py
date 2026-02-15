#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "services" / "ml"))

from ml_core.segment_and_detect import SegmentAndCatalogPipeline
from ml_core.shirt_catalog import OpenAIQuotaExceededError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s or "dataset"


def _as_data_url_from_pil(image: Image.Image) -> str:
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=88)
    raw = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{raw}"


def _as_data_url_from_path(path: Path) -> str:
    image = Image.open(path).convert("RGB")
    return _as_data_url_from_pil(image)


def _try_embed_remote_image(url: str | None, timeout: int = 12) -> str | None:
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "image" not in content_type:
            return None
        mime = content_type.split(";")[0].strip() or "image/jpeg"
        raw = base64.b64encode(resp.content).decode("utf-8")
        return f"data:{mime};base64,{raw}"
    except Exception:
        return None


def _collect_images(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        items = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    else:
        items = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    return sorted(items, key=lambda p: str(p).lower())


def _build_page(items: list[dict[str, Any]], initial_k: int, max_k: int) -> str:
    payload = json.dumps(items)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Catalog Dataset Report</title>
  <style>
    :root {{
      --bg: #f3f0e8;
      --ink: #201d19;
      --muted: #6b655c;
      --panel: #fffdf8;
      --line: #d8d2c3;
      --accent: #1f5c65;
    }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 0%, #efe7d5 0, transparent 30%),
        radial-gradient(circle at 88% 2%, #dceff2 0, transparent 28%),
        var(--bg);
    }}
    .wrap {{ max-width: 1220px; margin: 0 auto; padding: 18px; }}
    .controls {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}
    .btn {{
      border: 0;
      border-radius: 10px;
      background: #183e45;
      color: #fff;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 600;
    }}
    .pill {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 10px;
    }}
    select {{
      border-radius: 8px;
      border: 1px solid #c9c3b5;
      padding: 5px;
      background: #fff;
    }}
    .lead {{
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .leadimg {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
      min-height: 320px;
      display: grid;
      place-items: center;
    }}
    .leadimg img {{
      width: 100%;
      max-height: 520px;
      object-fit: contain;
      background: #fff;
    }}
    .meta {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 14px;
    }}
    .meta p {{ margin: 6px 0; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
    }}
    .card img {{
      width: 100%;
      height: 210px;
      object-fit: contain;
      border: 1px solid #ede7da;
      border-radius: 10px;
      background: white;
    }}
    .noimg {{
      height: 210px;
      border: 1px dashed var(--line);
      border-radius: 10px;
      display: grid;
      place-items: center;
      color: var(--muted);
      background: #faf7f0;
    }}
    h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
    h3 {{ margin: 9px 0 6px 0; font-size: 15px; line-height: 1.35; }}
    .price {{ margin: 0 0 6px 0; color: var(--accent); font-weight: 700; }}
    .small {{ margin: 0 0 7px 0; font-size: 12px; color: var(--muted); }}
    a {{ font-size: 12px; color: #164a52; word-break: break-all; }}
    @media (max-width: 880px) {{
      .lead {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="controls">
      <button id="prev" class="btn">Prev</button>
      <button id="next" class="btn">Next</button>
      <span class="pill">Image: <strong id="idx"></strong></span>
      <span class="pill">Top items:
        <select id="k"></select>
      </span>
      <span class="pill">Use keyboard: left/right arrows</span>
    </div>

    <section class="lead">
      <div class="leadimg"><img id="inputImg" alt="input-image" /></div>
      <div class="meta">
        <h1 id="name"></h1>
        <p><strong>status:</strong> <span id="status"></span></p>
        <p><strong>garment:</strong> <span id="garment"></span></p>
        <p><strong>brand_hint:</strong> <span id="brand"></span></p>
        <p><strong>exact_item_hint:</strong> <span id="exact"></span></p>
        <p><strong>confidence:</strong> <span id="conf"></span></p>
        <p><strong>queries:</strong> <span id="queries"></span></p>
      </div>
    </section>

    <section id="grid" class="grid"></section>
  </div>

  <script>
    const data = {payload};
    const maxK = {max_k};
    let topK = {initial_k};
    let i = 0;

    const el = {{
      idx: document.getElementById("idx"),
      inputImg: document.getElementById("inputImg"),
      name: document.getElementById("name"),
      status: document.getElementById("status"),
      garment: document.getElementById("garment"),
      brand: document.getElementById("brand"),
      exact: document.getElementById("exact"),
      conf: document.getElementById("conf"),
      queries: document.getElementById("queries"),
      grid: document.getElementById("grid"),
      k: document.getElementById("k"),
    }};

    for (let n = 1; n <= maxK; n++) {{
      const opt = document.createElement("option");
      opt.value = String(n);
      opt.textContent = String(n);
      if (n === topK) opt.selected = true;
      el.k.appendChild(opt);
    }}
    el.k.addEventListener("change", () => {{
      topK = parseInt(el.k.value, 10);
      render();
    }});

    function card(m) {{
      const img = m.image_data_url
        ? `<img src="${{m.image_data_url}}" alt="result" loading="lazy" />`
        : (m.image_url
            ? `<img src="${{m.image_url}}" alt="result" loading="lazy" />`
            : `<div class="noimg">No image</div>`);
      return `
        <article class="card">
          ${{img}}
          <h3>${{escapeHtml(m.title || "")}}</h3>
          <p class="price">${{escapeHtml(m.price_text || "(no price)")}}</p>
          <p class="small">score=${{Number(m.score || 0).toFixed(2)}} | source=${{escapeHtml(m.source || "unknown")}}</p>
          <p class="small">query: ${{escapeHtml(m.query || "")}}</p>
          <a href="${{escapeAttr(m.product_url || "#")}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(m.product_url || "")}}</a>
        </article>
      `;
    }}

    function escapeHtml(str) {{
      return (str || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }}
    function escapeAttr(str) {{
      return escapeHtml(str).replaceAll('"', "&quot;");
    }}

    function render() {{
      const row = data[i];
      el.idx.textContent = `${{i + 1}} / ${{data.length}}`;
      el.inputImg.src = row.input_image_data_url || "";
      el.name.textContent = row.name || "";
      el.status.textContent = row.status || "";
      el.garment.textContent = row.garment_name || "";
      el.brand.textContent = row.brand_hint || "None";
      el.exact.textContent = row.exact_item_hint || "None";
      el.conf.textContent = Number(row.confidence || 0).toFixed(2);
      el.queries.textContent = (row.queries || []).slice(0, 6).join(" | ");

      const items = (row.matches || []).slice(0, topK);
      el.grid.innerHTML = items.map(card).join("");
    }}

    function next() {{
      i = (i + 1) % data.length;
      render();
    }}
    function prev() {{
      i = (i - 1 + data.length) % data.length;
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
    parser = argparse.ArgumentParser(
        description=(
            "Run OpenAI->Serp pipeline across a folder and build one interactive HTML report "
            "where image and model options change with Prev/Next and top-k toggle."
        )
    )
    parser.add_argument("--dir", default="tests/web_detection/test_images", help="Image folder")
    parser.add_argument("--recursive", action="store_true", help="Include nested folders")
    parser.add_argument("--limit-images", type=int, default=0, help="Number of input images to process (0 means all)")
    parser.add_argument("--garment", default="top", help="Garment type")
    parser.add_argument("--top-k-max", type=int, default=10, help="Max results to fetch/store per image")
    parser.add_argument("--initial-top-k", type=int, default=5, help="Initial top-k shown in HTML toggle")
    parser.add_argument("--sleep-between-images", type=float, default=2.0, help="Seconds to sleep between images")
    parser.add_argument("--rich-context", action="store_true", help="Use exact-item context in query generation")
    parser.add_argument(
        "--out",
        default="tests/web_detection/_reports/catalog_dataset_report.html",
        help="Output HTML file",
    )
    args = parser.parse_args()

    if args.top_k_max < 1:
        print("--top-k-max must be >= 1")
        return 1
    if args.initial_top_k < 1:
        print("--initial-top-k must be >= 1")
        return 1
    if args.initial_top_k > args.top_k_max:
        print("--initial-top-k cannot exceed --top-k-max")
        return 1
    if args.limit_images < 0:
        print("--limit-images must be >= 0")
        return 1

    root = Path(args.dir)
    if not root.exists() or not root.is_dir():
        print(f"Invalid image directory: {root}")
        return 1

    images = _collect_images(root, recursive=args.recursive)
    if not images and not args.recursive:
        images = _collect_images(root, recursive=True)
    if not images:
        print(f"No images found in: {root}")
        return 1
    if args.limit_images > 0:
        images = images[: args.limit_images]

    pipeline = SegmentAndCatalogPipeline()
    rows: list[dict[str, Any]] = []

    for idx, image_path in enumerate(images, start=1):
        print(f"[{idx}/{len(images)}] {image_path}")
        try:
            result = pipeline.run(
                str(image_path),
                garment_type=args.garment,
                top_k=args.top_k_max,
                use_rich_context=args.rich_context,
            )
        except OpenAIQuotaExceededError as exc:
            print(f"PAUSED: {exc}")
            return 2
        except Exception as exc:
            print(f"FAIL: {image_path} ({type(exc).__name__}: {exc})")
            continue

        matches: list[dict[str, Any]] = []
        for m in result.catalog.matches[: args.top_k_max]:
            matches.append(
                {
                    "title": m.title,
                    "product_url": m.product_url,
                    "source": m.source,
                    "price_text": m.price_text,
                    "price_value": m.price_value,
                    "image_url": m.image_url,
                    "image_data_url": _try_embed_remote_image(m.image_url),
                    "query": m.query,
                    "score": m.score,
                }
            )

        rows.append(
            {
                "name": image_path.name,
                "path": str(image_path.as_posix()),
                "input_image_data_url": _as_data_url_from_path(image_path),
                "status": result.catalog.status,
                "garment_name": result.catalog.signal.garment_name,
                "brand_hint": result.catalog.signal.brand_hint,
                "exact_item_hint": result.catalog.signal.exact_item_hint,
                "confidence": result.catalog.signal.confidence,
                "queries": result.catalog.queries,
                "matches": matches,
            }
        )
        if args.sleep_between_images > 0 and idx < len(images):
            time.sleep(args.sleep_between_images)

    if not rows:
        print("No successful pipeline outputs were collected.")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_build_page(rows, args.initial_top_k, args.top_k_max), encoding="utf-8")
    print(f"report={out}")
    print(f"images_processed={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
