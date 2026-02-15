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

## Real-Time Video Streaming Pipeline

In addition to single-capture mode, the system supports a live video streaming pipeline:

1. Meta Ray-Ban DAT stream enters the companion app at 24 fps via `DatService`.
2. `StreamRelayService` relays frames to backend over a WebSocket (`ws://.../v1/stream`).
3. Client-side rate limiting drops excess frames (target ~10 fps to backend).
4. Server `VideoStreamPipeline` ingests each JPEG frame:
   - Decodes to grayscale thumbnail for fast perceptual comparison.
   - `KeyframeSelector` decides whether the scene has changed enough (SSIM + pixel diff).
   - Only keyframes (typically 1-3 per scene change) enter the ML processing buffer.
5. Background processing thread runs `CapturePipeline.run()` on each keyframe.
6. Results (garment detections, attributes) stream back via WebSocket.
7. Mobile app renders live overlay chips on the camera preview.

### Keyframe Selection Parameters

| Parameter              | Default | Description                                  |
|------------------------|---------|----------------------------------------------|
| `ssim_threshold`       | 0.85    | SSIM above this ⇒ "same scene", skip.       |
| `pixel_diff_threshold` | 0.06    | Mean absolute diff below this ⇒ skip.       |
| `min_interval_s`       | 1.0     | Minimum seconds between keyframes.           |
| `max_interval_s`       | 10.0    | Force keyframe after this many seconds.      |

All parameters can be tuned live via the `configure` WebSocket command.

### WebSocket Protocol

- **Binary messages (client → server):** Raw JPEG frame bytes.
- **Text/JSON (client → server):** `configure`, `ping`, `stats`, `stop`.
- **Text/JSON (server → client):** `ack`, `result`, `stats`, `pong`, `error`.

## Performance Considerations

- Lazy singleton model load in embedder.
- FAISS index loaded once and reused.
- Async processing via Celery to keep single-capture endpoint fast.
- Product embeddings precomputed by script.
- Video stream pipeline: keyframe selection avoids redundant ML work (typically processes <5% of incoming frames).
- WebSocket binary frames avoid HTTP overhead for continuous streaming.
- Client-side frame dropping reduces bandwidth to ~10 fps.

## Privacy Constraints

- Full scene frames are never persisted.
- API stores only cropped/blurred images.
- Safety blur pass runs server-side regardless of mobile blur.
- Video stream frames are processed in-memory and never written to disk.