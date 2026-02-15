# Aesthetica Monorepo

Spatial fashion capture and taste intelligence MVP for Meta Ray-Ban smart glasses.

Detailed setup: `docs/setup.md`

## Monorepo Layout

- `apps/mobile-capture` Flutter companion app with DAT abstraction, frame preprocessing, upload.
- `apps/ui-aesthetica` Next.js landing page + dashboard (App Router).
- `apps/dashboard-web` Legacy React + Vite dashboard (kept for reference).
- `services/api` FastAPI API, auth, capture ingestion, DB models, endpoints.
- `services/worker` Celery worker for async inference pipeline.
- `services/ml` Shared ML pipeline code: segmentation, embeddings, attributes, FAISS, radar.
- `infra` Docker Compose for local dev stack.
- `docs` Architecture and API notes.
- `data` Demo catalog, FAISS artifacts, uploads.

## Prerequisites

- Docker + Docker Compose
- Python 3.11+ (optional, for local non-docker runs)
- Node 20+ and pnpm/npm (dashboard local run)
- Flutter 3.24+ (mobile app)

## Quick Start (Docker)

1. Copy env:

```bash
cp .env.example .env
```

2. Start infra + services:

```bash
make dev
```

3. Run DB migrations and seed demo data:

```bash
make migrate
make seed
```

4. Build product embeddings + FAISS indexes:

```bash
make embed-products
```

API: `http://localhost:8000`  
Dashboard: `http://localhost:5173`
Catalog API: `http://localhost:8001`

## Running Services Individually

### API + Worker + DB with Docker Compose

```bash
docker compose -f infra/docker-compose.yml up --build
```

### UI (Landing + Dashboard)

```bash
make ui
```

This serves:
- Landing: `http://localhost:5173/`
- Dashboard: `http://localhost:5173/dashboard`

### Mobile Capture (Flutter)

```bash
cd apps/mobile-capture
flutter pub get
flutter run
```

Dev notes for DAT integration:
- The app uses `DatService` abstraction (`MethodChannel`) so native DAT SDK integration can be plugged in on iOS/Android.
- iOS bridge is now implemented in `apps/mobile-capture/ios/Runner/AppDelegate.swift` with:
  - DAT provider path (`MWDATCore` + `MWDATCamera`, when SPM dependency is installed)
  - AVFoundation fallback stream path (phone camera)
- Hardware camera-button capture is wired through DAT `photoDataPublisher` to auto-upload flow.
- Capture trigger supports in-app button; extendable for physical button callbacks and volume-button shortcut.

## Product Catalog + Indexing

- Source CSV: `data/products.csv`
- Embedding script: `services/ml/scripts/embed_products.py`
- FAISS output: `data/faiss/*.index` and `data/faiss/*_mapping.json`
- Open-web match fallback: SerpAPI Google Shopping (+ optional Google Lens when public image URLs are available)

## Environment Variables

See `.env.example`.

Key ones:
- `DATABASE_URL`
- `REDIS_URL`
- `FAISS_DIR`
- `PRODUCT_CSV_PATH`
- `OPENCLIP_MODEL_NAME`
- `OPENCLIP_PRETRAINED`
- `POKE_API_KEY`
- `SERPAPI_API_KEY` (for live online-shop search beyond local catalog)

## API Docs

- OpenAPI UI: `http://localhost:8000/docs`
- Human-readable spec: `docs/api.md`

## Tests

```bash
make test
```

Includes:
- Unit tests for embedding/radar math.
- Integration test for capture pipeline (mock model providers).

## Security + Privacy (MVP)

- Stores only cropped/blurred capture image.
- Runs backend safety face blur pass before persistence.
- No full scene frame persisted.
- Basic capture endpoint rate limit.

## Operations

- Health: `/healthz`, `/readyz`
- JSON structured logs with request/capture correlation IDs.
- Celery async jobs with retry support.

## Catalog API (Restored)

Dedicated endpoint for image -> OpenAI -> Serp -> DB write:

- `POST http://localhost:8001/v1/catalog/from-image`
- No auth
- Accepts multipart `image` upload or raw `image/jpeg` body
- Uploads the input image to Supabase Storage bucket `captures` (best effort) when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set
- Runs additional style-recommendation flow immediately:
  - OpenAI call #1: style description + 5 scores (0-100) into `style_scores`
  - Aggregate last 5 score rows/descriptions
  - OpenAI call #2: recommendation rationale + search query
  - One Serp shopping call -> top 5 rows into `style_recommendations`

Run (from repo root):

```bash
cp .env.example .env
# set these for storage upload of API input images
# SUPABASE_URL=https://<project-ref>.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
docker compose -f infra/docker-compose.yml up -d --build postgres redis api catalog-api
make migrate
```

Test with any local image file (example below uses one that exists in this repo):

```bash
curl -sS -X POST "http://localhost:8001/v1/catalog/from-image" -F "image=@apps/ui-aesthetica/public/images/outfit-1.png"
```

Verify latest writes in the configured database:

```bash
docker compose -f infra/docker-compose.yml run --rm api sh -lc 'python - <<\"PY\"
from sqlalchemy import create_engine, text
from app.core.config import settings
engine = create_engine(settings.database_url)
with engine.connect() as c:
    print("catalog_requests:", c.execute(text("select count(*) from catalog_requests")).scalar())
    print("style_scores:", c.execute(text("select count(*) from style_scores")).scalar())
    print("style_recommendations:", c.execute(text("select count(*) from style_recommendations")).scalar())
PY'
```

Quick health checks:

```bash
curl -s http://localhost:8001/healthz
curl -s http://localhost:8001/readyz
```

### Lens -> Shopping Smoke Test (No Integration Suite Required)

This script runs a real image through:
1. `POST /v1/catalog/from-image`
2. Supabase capture upload URL check
3. Serp Google Lens on that uploaded image
4. OpenAI `gpt-5.2` refinement (image + Lens normalized text) to remove non-clothing terms
5. Serp Google Shopping using the refined clothing-only description

Run from repo root:

```bash
docker compose -f infra/docker-compose.yml run --rm api \
  python services/api/app/scripts/test_lens_shopping_pipeline.py \
  --image apps/ui-aesthetica/public/images/outfit-1.png \
  --api-base http://catalog-api:8000
```

Or use Make:

```bash
make test-lens-shopping
# custom image:
make test-lens-shopping LENS_TEST_IMAGE=apps/ui-aesthetica/public/images/outfit-9.png
```

The script prints:
- `request_id`
- `capture_blob_url` + HTTP status
- `base_description` (raw Lens-normalized text)
- `refined_description` (OpenAI 5.2 cleaned clothing-only text)
- `normalized_description` (final query used for shopping)
- top Shopping results used by the Lens -> Shopping path
