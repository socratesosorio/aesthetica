# Web Detection Folder (Current Use)

This folder hosts the active OpenAI -> SerpAPI shirt catalog test tools.

## Active Scripts

- `tests/web_detection/run_catalog_one.py`
- `tests/web_detection/run_catalog_batch.py`
- `tests/web_detection/run_catalog_visual.py`
- `tests/web_detection/run_catalog_visual_dataset.py`
- `tests/web_detection/download_seed_images.py`
- `tests/web_detection/view_dataset.py`

## What It Does

For every test image:

1. Runs `SegmentAndCatalogPipeline`.
2. Prints top matches with links.
3. Optional assertion mode checks top-5 shopping matches are related to filename tokens.
4. Visual mode generates an HTML page with input image + result thumbnails + prices + links.
5. Dataset visual mode generates one interactive HTML report across many images:
   - Prev/Next changes the input image and its model outputs.
   - top-k dropdown changes how many returned products are shown.

## 30 Shirt Seed URLs

- `tests/web_detection/seed_shirt_urls.txt` contains 30 public shirt/person-with-shirt image URLs.

## Run

```bash
cd /Users/user/Desktop/Repos/aesthetica
export OPENAI_API_KEY=...
export SERPAPI_API_KEY=...
export PYTHONPATH=services/ml
export OPENAI_MIN_INTERVAL_SEC=4
export OPENAI_MAX_RETRIES=6
export SHIRT_MAX_SERP_QUERIES=1
export SHIRT_ENABLE_SERP_FALLBACK_QUERY=0

# Output mode (default)
./.venv/bin/python tests/web_detection/run_catalog_batch.py --sleep-between-images 4 --rich-context

# Assertion mode
./.venv/bin/python tests/web_detection/run_catalog_batch.py --sleep-between-images 4 --rich-context --assert-related

# Visual report for one image (local or URL input)
./.venv/bin/python tests/web_detection/run_catalog_visual.py tests/web_detection/test_images/essentials.jpg --top-k 10 --rich-context

# Interactive visual report for a folder (pipeline is run per image)
./.venv/bin/python tests/web_detection/run_catalog_visual_dataset.py --dir tests/web_detection/test_images --limit-images 5 --top-k-max 8 --initial-top-k 5 --rich-context --out tests/web_detection/_reports/catalog_dataset_report_5.html
open tests/web_detection/_reports/catalog_dataset_report_5.html

# Download the 30 seed images into your dataset folder
./.venv/bin/python tests/web_detection/download_seed_images.py --out-dir tests/web_detection/test_images/seed30

# Arrow-based dataset viewer (all images in folder)
./.venv/bin/python tests/web_detection/view_dataset.py --dir tests/web_detection/test_images/seed30 --out tests/web_detection/_reports/dataset_viewer.html
open tests/web_detection/_reports/dataset_viewer.html

# Arrow-based dataset viewer (limit to first 12 images)
./.venv/bin/python tests/web_detection/view_dataset.py --dir tests/web_detection/test_images/seed30 --limit 12 --out tests/web_detection/_reports/dataset_viewer_12.html
open tests/web_detection/_reports/dataset_viewer_12.html

# If you split lines, use "\" line continuations:
./.venv/bin/python tests/web_detection/view_dataset.py \
  --dir tests/web_detection/test_images/seed30 \
  --limit 12 \
  --out tests/web_detection/_reports/dataset_viewer_12.html
```

Visual output is written to:

- `tests/web_detection/_reports/<image_name>_report.html`
- `tests/web_detection/_reports/catalog_dataset_report_<N>.html`

Expected assertion-mode success:

- `PASS: all <N> image(s) returned related top-5 results`

## Notes

- If OpenAI quota is exhausted, the run pauses with a clear message.
- Brand hints for retrieval are sourced from ChatGPT analysis only.
