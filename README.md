# Aesthetica Monorepo

Spatial fashion capture and taste intelligence MVP for Meta Ray-Ban smart glasses.

Detailed setup: `docs/setup.md`

## Monorepo Layout

- `apps/mobile-capture` Flutter companion app with DAT abstraction, frame preprocessing, upload.
- `apps/dashboard-web` React + Vite mobile-first dashboard.
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

## Running Services Individually

### API + Worker + DB with Docker Compose

```bash
docker compose -f infra/docker-compose.yml up --build
```

### Dashboard Web

```bash
cd apps/dashboard-web
npm install
npm run dev
```

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
