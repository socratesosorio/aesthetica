#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import re
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "services" / "ml"))

from ml_core.segment_and_detect import SegmentAndCatalogPipeline
from ml_core.shirt_catalog import OpenAIQuotaExceededError


def _load_image(image_arg: str) -> tuple[str, str | Image.Image]:
    if image_arg.startswith("http://") or image_arg.startswith("https://"):
        resp = requests.get(image_arg, timeout=30)
        resp.raise_for_status()
        image = Image.open(BytesIO(resp.content)).convert("RGB")
        return image_arg, image

    p = Path(image_arg)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    return p.name, str(p)


def _input_img_src(image_arg: str, image_input: str | Image.Image) -> str:
    if image_arg.startswith("http://") or image_arg.startswith("https://"):
        return image_arg
    image = Image.open(Path(image_input)).convert("RGB")
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return s or "catalog_report"


def _build_html(
    title: str,
    input_img_src: str,
    result,
    top_k: int,
) -> str:
    cards: list[str] = []
    for i, m in enumerate(result.catalog.matches[:top_k]):
        embedded = _embed_remote_image(m.image_url)
        img_src = html.escape(embedded or (m.image_url or ""))
        img_block = (
            f'<img src="{img_src}" alt="result-{i}" loading="lazy" />'
            if img_src
            else '<div class="noimg">No image</div>'
        )
        cards.append(
            "<article class='card'>"
            f"{img_block}"
            f"<h3>{html.escape(m.title)}</h3>"
            f"<p class='price'>{html.escape(m.price_text or '(no price)')}</p>"
            f"<p class='meta'>score={m.score:.2f} | source={html.escape(m.source or 'unknown')}</p>"
            f"<p class='query'>query: {html.escape(m.query)}</p>"
            f"<a href='{html.escape(m.product_url)}' target='_blank' rel='noopener noreferrer'>{html.escape(m.product_url)}</a>"
            "</article>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Catalog Visual Report</title>
  <style>
    :root {{
      --bg: #f5f2ea;
      --ink: #1f1d1a;
      --muted: #6b6458;
      --panel: #fffdf8;
      --line: #ddd4c4;
      --accent: #1d5f6c;
    }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% 10%, #efe7d7 0, transparent 35%),
        radial-gradient(circle at 80% 0%, #d9ecef 0, transparent 30%),
        var(--bg);
    }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    .lead {{
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 18px;
      align-items: start;
      margin-bottom: 18px;
    }}
    .lead img {{
      width: 100%;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: white;
      object-fit: cover;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px 16px;
    }}
    .meta p {{ margin: 6px 0; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
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
      border-radius: 10px;
      background: #fff;
      border: 1px solid #eee7da;
    }}
    .noimg {{
      height: 210px;
      border-radius: 10px;
      border: 1px dashed var(--line);
      display: grid;
      place-items: center;
      color: var(--muted);
      background: #faf7f0;
    }}
    h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
    h3 {{ margin: 10px 0 6px 0; font-size: 15px; line-height: 1.35; }}
    .price {{ margin: 0 0 4px 0; font-weight: 700; color: var(--accent); }}
    .query, .meta {{ margin: 0 0 8px 0; color: var(--muted); font-size: 12px; }}
    a {{ color: #14404a; font-size: 12px; word-break: break-all; }}
    @media (max-width: 860px) {{
      .lead {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="lead">
      <img src="{html.escape(input_img_src)}" alt="input-image" />
      <section class="panel meta">
        <h1>{html.escape(title)}</h1>
        <p><strong>status:</strong> {html.escape(result.catalog.status)}</p>
        <p><strong>garment:</strong> {html.escape(result.catalog.signal.garment_name)}</p>
        <p><strong>brand_hint:</strong> {html.escape(str(result.catalog.signal.brand_hint))}</p>
        <p><strong>exact_item_hint:</strong> {html.escape(str(result.catalog.signal.exact_item_hint))}</p>
        <p><strong>confidence:</strong> {result.catalog.signal.confidence:.2f}</p>
        <p><strong>queries:</strong> {html.escape(" | ".join(result.catalog.queries[:6]))}</p>
      </section>
    </div>
    <section class="grid">
      {''.join(cards)}
    </section>
  </div>
</body>
</html>"""


def _embed_remote_image(url: str | None) -> str | None:
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "image" not in content_type:
            return None
        mime = content_type.split(";")[0].strip() or "image/jpeg"
        raw = base64.b64encode(resp.content).decode("utf-8")
        return f"data:{mime};base64,{raw}"
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run OpenAI->Serp pipeline and generate visual HTML report with result thumbnails and prices."
    )
    parser.add_argument("image", help="Path or URL to input image")
    parser.add_argument("--garment", default="top", help="Garment type")
    parser.add_argument("--top-k", type=int, default=10, help="Number of matches to render")
    parser.add_argument("--rich-context", action="store_true", help="Use exact_item_hint/context_terms when building queries")
    parser.add_argument(
        "--out",
        default="tests/web_detection/_reports",
        help="Output directory for the generated HTML report",
    )
    args = parser.parse_args()

    try:
        display_name, image_input = _load_image(args.image)
    except Exception as exc:
        print(f"Failed to load image: {type(exc).__name__}: {exc}")
        return 1

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
    except Exception as exc:
        print(f"Pipeline failed: {type(exc).__name__}: {exc}")
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{_slug(display_name)}_report.html"
    input_src = _input_img_src(args.image, image_input)
    page = _build_html(display_name, input_src, result, args.top_k)
    out_file.write_text(page, encoding="utf-8")

    print(f"report={out_file}")
    print(f"status={result.catalog.status}")
    print(f"garment={result.catalog.signal.garment_name}")
    print(f"brand_hint={result.catalog.signal.brand_hint}")
    print(f"matches={len(result.catalog.matches[:args.top_k])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
