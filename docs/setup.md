# Aesthetica Setup Guide

This guide gets the full local MVP running: API, worker, DB, dashboard, and iOS mobile capture.

## Prerequisites

- Docker Desktop (with Compose)
- Node.js 20+
- Flutter 3.24+ (for mobile app)
- Xcode 15+ (for iOS DAT integration)

## 1) Clone and configure env

From repo root:

```bash
cp .env.example .env
```

If you need to override secrets/URLs, edit `.env` before starting services.

For open-web product matching (any online shop via Google Shopping API surface), set:

- `SERPAPI_API_KEY=<your key>`
- keep `WEB_SEARCH_ENABLED=true`

## 2) Start backend stack

```bash
make dev
```

This starts:
- `postgres` on `localhost:5432`
- `redis` on `localhost:6379`
- `api` on `http://localhost:8000`
- `worker` (Celery queue consumer)
- `minio` (optional S3-compatible local object store)

## 3) Initialize database and catalog

Open a second terminal in repo root:

```bash
make migrate
make seed
make embed-products
```

What these do:
- `migrate`: applies Alembic migrations
- `seed`: creates demo user + ingests `data/products.csv`
- `embed-products`: builds product embeddings + FAISS indexes under `data/faiss/`

## 4) Start dashboard web app

Open a third terminal:

```bash
cd apps/dashboard-web
npm install
npm run dev
```

Open `http://localhost:5173`.

## 5) Login credentials (dev)

- Email: `demo@aesthetica.dev`
- Password: `demo123`

## 6) Validate core endpoints

- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/healthz`
- Ready: `http://localhost:8000/readyz`

## 7) iOS mobile capture + DAT setup

### 7.1 Add DAT iOS SDK in Xcode

Open `apps/mobile-capture/ios/Runner.xcworkspace`, then add Swift Package:

- `https://github.com/facebook/meta-wearables-dat-ios`

Attach package products to `Runner` target (at minimum `MWDATCore` and `MWDATCamera`).

### 7.2 Configure Info.plist

Edit `apps/mobile-capture/ios/Runner/Info.plist` and set:

- `MWDAT.MetaAppID`
- `MWDAT.ClientToken`

Ensure URL scheme consistency:

- `CFBundleURLTypes -> CFBundleURLSchemes`: `aesthetica-mobile-capture`
- `MWDAT.AppLinkURLScheme`: `aesthetica-mobile-capture`

Keep fallback disabled for glasses testing:

- `AESTHETICA_FORCE_PHONE_CAMERA_FALLBACK = false`

### 7.3 Pair and run

1. Pair glasses in Meta AI app first.
2. From repo root:

```bash
cd apps/mobile-capture
flutter pub get
flutter run --dart-define=USE_MOCK_DAT=false --dart-define=API_BASE_URL=http://127.0.0.1:8000 --dart-define=API_TOKEN=dev
```

If running on physical iPhone, replace `127.0.0.1` with your Mac LAN IP (for example `http://192.168.1.42:8000`).

## 8) End-to-end smoke test

1. Launch mobile app and connect stream.
2. Trigger capture (in-app button or DAT photo callback).
3. Confirm API `POST /v1/captures` returns `queued`.
4. Worker processes capture to `done`.
5. Refresh dashboard `Looks` and `Profile` pages to see results.

## 9) Useful commands

From repo root:

```bash
make logs
make test
make down
```

- `make logs`: tail API + worker logs
- `make test`: run API test suite in container
- `make down`: stop and remove stack volumes

## Troubleshooting

- Dashboard cannot call API from browser:
  - Ensure API is up on `http://localhost:8000`
  - Ensure dashboard uses default `VITE_API_BASE_URL` or set it explicitly.
- Capture stuck in `queued`:
  - Check `make logs` for worker errors.
  - Verify Redis and worker are running.
- iPhone app cannot hit API:
  - Use Mac LAN IP, not `127.0.0.1`.
  - Ensure phone and Mac are on same network.
- Only local catalog products appear in matches:
  - Set `SERPAPI_API_KEY` in `.env`.
  - Ensure outbound network access from API container.
