# Aesthetica Monorepo

Spatial fashion capture and taste intelligence MVP for Meta Ray-Ban smart glasses.

Detailed setup: `docs/setup.md`

## Monorepo Layout

- `apps/mobile-capture`: Flutter companion app.
- `apps/dashboard-web`: React + Vite dashboard.
- `services/api`: FastAPI backend.
- `services/worker`: Celery worker.
- `services/ml`: ML pipelines and retrieval logic.
- `infra`: Docker Compose setup.
- `tests`: integration and pipeline tests.

## Quick Start (Docker)

```bash
cp .env.example .env
make dev
make migrate
make seed
```

- API: `http://localhost:8000`
- Dashboard: `http://localhost:5173`

## Image-To-Link Pipeline (Current Spec)

This repo now supports a shirt-focused 2-stage retrieval flow:

1. Stage 1: image understanding (garment context extraction).
2. Stage 2: SerpAPI shopping retrieval + reranking.

Behavior aligned to spec:

- Input: images from `tests/web_detection/test_images`.
- Success criterion: top 5 results include terms related to the image name.
- Matching: normalized filename tokens; synonym/alias tolerant matching.
- Ranking preference: direct product pages are prioritized over generic search pages.
- Segmentation: attempted, but pipeline also evaluates full image and picks the stronger result.
- OpenAI quota/rate-limit behavior: run pauses and asks for key/credits refresh.

Main modules:

- `services/ml/ml_core/shirt_catalog.py`
- `services/ml/ml_core/segment_and_detect.py`
- `tests/web_detection/run_catalog_batch.py`

## Environment Variables

Key variables:

- `OPENAI_API_KEY`
- `SERPAPI_API_KEY`
- `PYTHONPATH=services/ml`

Rate-limit controls:

- `OPENAI_MIN_INTERVAL_SEC` (default `2.5`)
- `OPENAI_MAX_RETRIES` (default `5`)

Cost/call controls:

- `SHIRT_MAX_SERP_QUERIES` (default `1`) limits shopping queries per image.
- `SHIRT_ENABLE_SERP_FALLBACK_QUERY` (default `0`) optionally runs one extra fallback query when first query returns nothing.

Pipeline call behavior (current):

- OpenAI: 1 extraction call per image
- SerpAPI: 1 query per image by default

## Run Single Image

```bash
cd /Users/user/Desktop/Repos/aesthetica
export OPENAI_API_KEY=...
export SERPAPI_API_KEY=...
export PYTHONPATH=services/ml

./.venv/bin/python tests/web_detection/run_catalog_one.py tests/web_detection/test_images/essentials.jpg --top-k 5 --rich-context

# Any local image
./.venv/bin/python tests/web_detection/run_catalog_one.py /absolute/path/to/photo.jpg --top-k 5 --rich-context

# Any image URL
./.venv/bin/python tests/web_detection/run_catalog_one.py "https://example.com/photo.jpg" --top-k 5 --rich-context

# Optional relevance check
./.venv/bin/python tests/web_detection/run_catalog_one.py tests/web_detection/test_images/dodgers.jpg --top-k 5 --rich-context --expect dodgers
```

## Visual Report (Image + Returned Items)

Generate a local HTML report that shows:
- input image
- returned item thumbnails
- title, price, source, query, and product URL

```bash
cd /Users/user/Desktop/Repos/aesthetica
export OPENAI_API_KEY=...
export SERPAPI_API_KEY=...
export PYTHONPATH=services/ml

./.venv/bin/python tests/web_detection/run_catalog_visual.py tests/web_detection/test_images/essentials.jpg --top-k 10 --rich-context
```

Output file:
- `tests/web_detection/_reports/<image_name>_report.html`

## Interactive Dataset Report (Prev/Next + Top-K Toggle)

Run pipeline across a folder and build one HTML page where:
- left/right changes the input image
- model results (links, prices, thumbnails) change with that image
- top-k dropdown controls how many product options are shown

```bash
cd /Users/user/Desktop/Repos/aesthetica
export OPENAI_API_KEY=...
export SERPAPI_API_KEY=...
export PYTHONPATH=services/ml

./.venv/bin/python tests/web_detection/run_catalog_visual_dataset.py --dir tests/web_detection/test_images --limit-images 5 --top-k-max 8 --initial-top-k 5 --sleep-between-images 0 --rich-context --out tests/web_detection/_reports/catalog_dataset_report_5.html
open tests/web_detection/_reports/catalog_dataset_report_5.html
```

## 30 Shirt Seed Images

Seed URL list:
- `tests/web_detection/seed_shirt_urls.txt`

Download them into your dataset:

```bash
cd /Users/user/Desktop/Repos/aesthetica
./.venv/bin/python tests/web_detection/download_seed_images.py --out-dir tests/web_detection/test_images/seed30
```

## Dataset Slideshow Viewer (Arrow Controls)

Create a local HTML viewer for dataset images with on-screen left/right arrows and keyboard arrow support.

```bash
cd /Users/user/Desktop/Repos/aesthetica

# View all images in a folder
./.venv/bin/python tests/web_detection/view_dataset.py --dir tests/web_detection/test_images/seed30 --out tests/web_detection/_reports/dataset_viewer.html
open tests/web_detection/_reports/dataset_viewer.html

# View only first N images (example: 15)
./.venv/bin/python tests/web_detection/view_dataset.py --dir tests/web_detection/test_images/seed30 --limit 15 --out tests/web_detection/_reports/dataset_viewer_15.html
open tests/web_detection/_reports/dataset_viewer_15.html
```

## Run Full Folder Validation

```bash
cd /Users/user/Desktop/Repos/aesthetica
export OPENAI_API_KEY=...
export SERPAPI_API_KEY=...
export PYTHONPATH=services/ml

# Slower mode to reduce 429s
export OPENAI_MIN_INTERVAL_SEC=4
export OPENAI_MAX_RETRIES=6
export SHIRT_MAX_SERP_QUERIES=1
export SHIRT_ENABLE_SERP_FALLBACK_QUERY=0

# Default: print results/links for each image (no pass/fail assertions)
./.venv/bin/python tests/web_detection/run_catalog_batch.py --sleep-between-images 4 --rich-context

# Optional: enforce related-token assertions against image filenames
./.venv/bin/python tests/web_detection/run_catalog_batch.py --sleep-between-images 4 --rich-context --assert-related
```

Assertion-mode expected success line:
- `PASS: all <N> image(s) returned related top-5 results`

## Test Commands

```bash
# Shirt catalog deterministic tests
./.venv/bin/pytest -q tests/shirt_catalog -k "not live_api"

# Optional live shirt test
export RUN_LIVE_SHIRT_CATALOG_TESTS=1
./.venv/bin/pytest -q tests/shirt_catalog/test_shirt_catalog.py -k live_api -s
```

## API Docs

- OpenAPI UI: `http://localhost:8000/docs`
- Human-readable spec: `docs/api.md`

## References

- `tests/web_detection/README.md`
- `tests/shirt_catalog/README.md`
- `docs/setup.md`
