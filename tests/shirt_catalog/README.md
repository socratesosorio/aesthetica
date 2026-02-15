# Shirt Catalog Tests

High-precision shirt-only product matching pipeline tests.

## Run deterministic tests (no network)

```bash
./.venv/bin/pytest -q tests/shirt_catalog/test_shirt_catalog.py -k "not live_api"
```

## Run live API test (OpenAI + SerpAPI)

```bash
export OPENAI_API_KEY=...
export SERPAPI_API_KEY=...
export RUN_LIVE_SHIRT_CATALOG_TESTS=1
./.venv/bin/pytest -q tests/shirt_catalog/test_shirt_catalog.py -k live_api -s
```

Live test image:
- `tests/web_detection/test_images/nike.jpg`

If that image is missing, run:

```bash
ls tests/web_detection/test_images
```
