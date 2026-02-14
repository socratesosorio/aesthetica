# Aesthetica Architecture (MVP)

## End-to-End Flow

1. Meta Ray-Ban stream enters companion mobile app via DAT integration abstraction (`DatService`).
2. Mobile app capture trigger (in-app button) grabs current frame.
3. On-device preprocessing: reticle crop, downscale, face blur, JPEG compress.
4. Mobile uploads to `POST /v1/captures` as multipart.
5. API applies safety blur pass, stores only processed crop, creates queued capture record.
6. API enqueues Celery job (`worker.tasks.process_capture`).
7. Worker runs shared ML pipeline:
   - segmentation parsing -> garment buckets + crops
   - global + per-garment embeddings (OpenCLIP or deterministic fallback)
   - attribute extraction heuristics
   - FAISS retrieval + price-tier alternatives
   - user taste embedding EMA + 5-axis radar projection
8. Worker persists garments/matches/profile/radar history and sends Poke summary.
9. Dashboard fetches captures/profile/history and renders mobile-first UI with D3 radar chart.

## Services

- `services/api`: FastAPI + SQLAlchemy + Alembic.
- `services/worker`: Celery worker process.
- `services/ml`: Shared ML modules (model loading cached, FAISS singleton).
- `apps/dashboard-web`: React + Vite dashboard.
- `apps/mobile-capture`: Flutter companion app.

## Data Stores

- Postgres: users, captures, garments, products, matches, profiles, radar history.
- Redis: Celery queue.
- Local filesystem (or S3-compatible): processed image storage.
- FAISS index files on disk under `data/faiss`.

## Performance Considerations

- Lazy singleton model load in embedder.
- FAISS index loaded once and reused.
- Async processing via Celery to keep capture endpoint fast.
- Product embeddings precomputed by script.

## Privacy Constraints

- Full scene frames are never persisted.
- API stores only cropped/blurred images.
- Safety blur pass runs server-side regardless of mobile blur.
