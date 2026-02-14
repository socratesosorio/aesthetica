You are a principal engineer + ML engineer + product engineer. You will generate a complete, runnable monorepo implementing the MVP described below, with production-grade structure, clear abstractions, tests, and local-dev Docker Compose.

PROJECT NAME
Aesthetica — Spatial Fashion Capture & Taste Intelligence for Meta Ray-Ban smart glasses

PRIMARY OUTCOME
Build an end-to-end system where:
1) A user captures an outfit from Meta Ray-Ban smart glasses (via Meta Wearables Device Access Toolkit “DAT” integrated into a companion mobile app).
2) The mobile app crops/filters and uploads an image frame to a FastAPI backend.
3) The backend performs:
   - human/clothing parsing (segmentation into garment regions)
   - CLIP-style embeddings (global + per-garment)
   - attribute extraction (color, minimalism, structure, formality, silhouette, pattern)
   - product similarity search over a pre-embedded product catalog (FAISS)
   - user taste profile updates (EMA embedding + interpretable 5-axis radar)
4) The system sends a result summary + links via Poke messaging.
5) The user can view saved looks + matches + taste radar + history via a mobile-first web dashboard.

IMPORTANT REAL-WORLD SDK CONSTRAINTS (DO NOT IGNORE)
- Meta Wearables Device Access Toolkit (DAT) is for mobile apps (iOS/Android) connecting to Meta AI glasses sensors (camera). The Meta AI app acts as the bridge for pairing/permissions.
- Current DAT preview constraints to respect:
  - Camera access is available; microphone/speaker via standard Bluetooth profiles.
  - No Meta Neural Band sensor access in preview.
  - Custom gesture controls like taps/swipes aren’t offered; only standard events (pause/resume/stop) may be available.
  - “Hey Meta” custom Meta AI voice command integration is NOT provided; but you can access device microphone to build your own voice commands in-app.
  - Video stream is constrained (Bluetooth); plan for max ~720p/30fps stream, and adaptive degradation.
  - Publishing integrations may be gated; still build as a functional dev/test MVP.
- Therefore: Implement capture trigger using one of these MVP-safe options:
  (A) In-app “Capture” button that requests a frame from the glasses stream.
  (B) Physical glasses capture button if stream exposes photo capture callbacks.
  (C) Optional: phone volume button as a capture shortcut.
  Provide clean abstraction so gesture/wristband triggers can be added later without refactor.

PRD REQUIREMENTS (MVP SCOPE)
Included:
- Companion mobile capture app with DAT integration
- Reticle-centered crop (fixed bounding box) + downscale + face blur (privacy)
- Backend inference pipeline:
  - segmentation / garment parsing
  - embeddings (global + per garment)
  - attribute extraction
  - product vector search (FAISS)
  - taste profile engine (EMA embedding + 5D radar)
- Poke integration: send user message after processing
- Mobile web dashboard: gallery of looks, look detail with matches, taste radar chart, history timeline, simple analytics

Excluded:
- Checkout integration
- Social features
- Full wardrobe tracking beyond captured looks
- Retail API partnerships beyond demo ingestion adapters

TECH STACK (USE THESE EXACT CHOICES)
Monorepo layout:
- /apps/mobile-capture (Flutter recommended for speed + cross-platform; may also choose React Native IF you can still integrate DAT cleanly)
- /apps/dashboard-web (React + Vite, mobile-first)
- /services/api (Python FastAPI)
- /services/worker (Python Celery worker OR RQ; choose Celery+Redis if you need retries)
- /services/ml (shared ML code: segmentation, embedding, attributes)
- /infra (Docker Compose, Nginx optional)
- /docs (architecture, API docs, runbooks)

Backend:
- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.0 + Alembic
- Postgres for metadata
- Redis for queue (if using Celery)
- Object storage: local filesystem in dev, S3-compatible interface abstraction (MinIO optional)
- Vector search: FAISS (persist index to disk; reload on boot)
- Embeddings: OpenCLIP (open_clip_torch) OR CLIP-compatible model; MUST output a fixed-dim vector (prefer 512D).
- Segmentation / human parsing:
  - Use “fashn-ai/fashn-human-parser” (SegFormer-B4 human parsing) OR the fashn-human-parser Python package for production-accurate preprocessing.
  - You MUST map its semantic classes to the PRD garment buckets:
    Top, Bottom, Outerwear (if not explicitly predicted, infer), Shoes (infer from “feet” region + bottom-of-frame heuristics OR extend with shoe detector later), Accessories (bag/hat/glasses/jewelry/scarf/belt).
  - Make segmentation pluggable to swap with another model later.

Frontend:
- React + TypeScript + Vite
- D3 for radar chart (pentagon)
- A simple component library allowed (e.g., Radix UI), but keep bundle light.
- Authentication: simple JWT session from backend (MVP) OR magic-link (optional). Keep it minimal.

Mobile capture app:
- MUST integrate Meta Wearables DAT:
  - Initialize SDK
  - Register with Meta AI app
  - Request camera permission via SDK
  - Start video stream (configurable quality + FPS)
  - Receive frames as bytes
  - Capture a single frame on user trigger and upload to backend
- Implement privacy preprocessing before upload:
  - Reticle-center crop: fixed relative box (e.g., 0.55w x 0.70h centered)
  - Downscale to inference size (e.g., long side 640 px)
  - Face blur: detect face(s) and blur
    - For MVP: do face detection/blur on device if feasible (Flutter plugin like MLKit). If too heavy, do it server-side as a fallback BUT keep on-device path as primary and required in code architecture.
  - Compress: JPEG quality ~70–85 to reduce latency.
- UX:
  - Minimal UI; big capture button; optional reticle overlay on preview
  - Capture confirmation animation (ring)
  - Display: “Captured” + “Sent” states
  - Do not implement browsing on glasses; all results arrive via Poke + dashboard.

PRODUCT CATALOG + VECTOR SEARCH REQUIREMENTS
- Implement a product catalog ingestion system that supports at least one demo source:
  Option 1 (recommended MVP): local dataset in /data/products.csv + /data/images/*
  Option 2: Shopify Storefront API adapter (optional)
- Each product record includes:
  product_id (uuid or stable string)
  title
  brand
  category (top/bottom/outerwear/shoes/accessories)
  price (number + currency)
  image_url OR local image path
  product_url
  color tags (optional)
- Precompute embeddings for each product image offline via a script:
  /services/ml/scripts/embed_products.py
- Build a FAISS index per category (or one index with metadata filter):
  - Persist index to /data/faiss/
  - Store mapping from faiss ids -> product_id in a sidecar json
- Retrieval per garment:
  - Query topK=30
  - Return:
    * closest match
    * lower-priced alternative (closest among results priced <= 0.8 * closest_price if possible)
    * premium alternative (closest among results priced >= 1.2 * closest_price)
  - If price missing, skip price-tier logic gracefully.

TASTE PROFILE ENGINE (CORE)
Implement:
1) User embedding (512D):
   user_embedding = alpha * previous + (1-alpha) * capture_embedding
   alpha default 0.85
2) Interpretable 5D radar axes:
   Minimal ↔ Maximal
   Structured ↔ Relaxed
   Neutral ↔ Color-Forward
   Classic ↔ Experimental
   Casual ↔ Formal

MVP IMPLEMENTATION STRATEGY FOR RADAR (NO TRAINING REQUIRED)
Implement radar projection without supervised training by using CLIP text embeddings to define axis vectors:
- For each axis, define two anchor phrases (examples):
  Minimal: "minimalist outfit, clean lines, muted palette"
  Maximal: "maximalist outfit, bold patterns, layered accessories"
  Structured: "structured tailoring, sharp silhouette"
  Relaxed: "relaxed fit, draped fabrics, casual silhouette"
  Neutral: "neutral tones outfit, beige, black, white"
  Color-Forward: "bright colorful outfit, saturated colors"
  Classic: "classic timeless outfit, traditional staples"
  Experimental: "avant-garde experimental outfit, unusual silhouettes"
  Casual: "casual everyday outfit"
  Formal: "formal outfit, eveningwear, business formal"
- Compute text embeddings, normalize, compute axis_vector = normalize(textB - textA).
- Score = dot(normalize(user_embedding), axis_vector)
- Convert to 0–100 using a calibrated mapping:
  mapped = clamp( (score * scale + bias), 0, 100 )
  Choose default scale ~50 and bias ~50, but store these as config and log distributions to refine.
- Store radar history over time.

Also store additional signals:
- Brand frequency
- Color distribution trend (from attribute extraction)
- Silhouette clustering (optional kmeans on embeddings)
- Category bias counts

CLOUD INFERENCE PIPELINE — REQUIRED MODULES
For each capture:
1) Validate input and store capture image (already cropped/blurred) in object storage.
2) Segmentation / parsing:
   - Produce class masks
   - Derive garment crops for each garment bucket
3) Embeddings:
   - Global outfit embedding
   - Per garment embedding for each available garment crop
4) Attribute extraction:
   - Color histogram in LAB or HSV; cluster k=3–5; return top colors as hex + percent
   - Pattern detection: simple heuristic (edge density + color entropy) -> solid vs patterned + confidence
   - Formality score: MVP heuristic using CLIP text similarity against "formal outfit" vs "casual outfit"
   - Minimalism score: CLIP similarity against "minimalist outfit" vs "maximalist outfit"
   - Structure score: CLIP similarity against "tailored structured outfit" vs "relaxed slouchy outfit"
   - Silhouette: coarse buckets (slim/regular/oversized) using CLIP prompts
   All heuristics must be deterministic, documented, and cached.
5) Product matching:
   - Use garment embeddings (preferred) else fallback to global embedding
   - Query FAISS indexes
6) Taste update:
   - Update user embedding + radar
7) Notify:
   - Send Poke message with summary + links
   - Persist all outputs in DB

POKE INTEGRATION REQUIREMENTS
- Implement a notifier module that can send a message via Poke using:
  POST https://poke.com/api/v1/inbound-sms/webhook
  Header: Authorization: Bearer ${POKE_API_KEY}
  Body: {"message": "..."}
- If POKE_API_KEY is missing, log warning and skip send (do not fail pipeline).
- Message format MUST be:
  1) One-line aesthetic summary (generated from attributes + radar)
  2) Radar delta (e.g., “+4 Structured, +2 Minimal”)
  3) Top matches list with short names + URLs (max 5 links)
  Keep message under ~800 chars.

MOBILE DASHBOARD REQUIREMENTS
Routes:
- /login (simple)
- /looks (gallery)
- /looks/:id (detail view)
- /profile (taste radar + summary)
- /analytics (lightweight: capture frequency, category bias, color trends)

UI:
- Gallery grid of captured looks
- Look detail:
  - original stored crop
  - garment breakdown thumbnails
  - matches per garment
- Taste radar:
  - D3 radar pentagon (0–100 scale)
  - show last updated date/time
  - show deltas since last capture
- Timeline:
  - radar evolution chart (simple line chart per axis OR snapshots)

SYSTEM ARCHITECTURE — MONOREPO OUTPUT EXPECTATIONS
You MUST output:
1) Complete folder structure (tree)
2) Every file’s full content
3) A top-level README with:
   - prerequisites
   - how to run backend + worker + db with docker-compose
   - how to run product embedding + index build scripts
   - how to run dashboard
   - how to run mobile app (dev notes for DAT)
   - environment variables list
4) API documentation (OpenAPI auto via FastAPI + a short human-readable /docs/ API spec)
5) Database migrations (Alembic)
6) Basic tests:
   - unit tests for embedding/radar math
   - integration test for capture pipeline (mock models)
7) Observability:
   - structured logging (json logs)
   - request id / capture id correlation
   - simple health endpoints: /healthz, /readyz
8) Performance considerations:
   - caching model loads (singleton)
   - avoid reloading FAISS per request
   - async job queue for inference

BACKEND API CONTRACT (MUST IMPLEMENT)
Auth:
- POST /v1/auth/login  (MVP: email + password OR dev token)
- GET  /v1/auth/me

Capture:
- POST /v1/captures
  Request: multipart image OR JSON with signed upload approach (choose one; simplest is multipart)
  Response: {capture_id, status:"queued"}
- GET /v1/captures/{capture_id}
  Response: capture record + processing status + results if done
- GET /v1/users/{user_id}/captures?limit=...

Results:
- GET /v1/users/{user_id}/profile
  Response: {user_embedding_meta, radar_vector, brand_stats, color_stats, category_bias}
- GET /v1/users/{user_id}/radar/history?days=...
- GET /v1/products/search (debug endpoint)
  Query: embedding vector (base64) or capture_id + garment_type

Internal:
- POST /v1/internal/reindex-products
- POST /v1/internal/recompute-radar (optional)

DATA MODEL (POSTGRES) — MINIMUM TABLES
- users
  id, email, password_hash, created_at
- captures
  id, user_id, created_at, image_path, status, error
- garments
  id, capture_id, garment_type, crop_path, embedding_vector (pgvector optional; else store in separate table), attributes_json
- products
  id, title, brand, category, price, currency, image_url, product_url, embedding_id
- matches
  id, capture_id, garment_id nullable, product_id, rank, similarity, match_group (closest/lower/premium)
- user_profiles
  user_id, embedding_vector, radar_vector_json, updated_at
- user_radar_history
  id, user_id, created_at, radar_vector_json
- user_stats (optional materialized aggregates)

If pgvector is NOT used, store embeddings as:
- float32 array serialized to bytes (base64) OR
- separate embeddings table with BYTEA
But retrieval does not require DB vector search (FAISS handles it).

ML IMPLEMENTATION DETAILS — DO THIS EXACTLY
Embeddings:
- Use OpenCLIP with a known model that outputs 512D; normalize vectors.
- Provide a config file for model name + pretrained weights.
- Add a script to validate embedding dimension and cosine similarity correctness.

Segmentation:
- Use FASHN Human Parser:
  - Inference returns segmentation map with class IDs.
  - Implement mapping to garment buckets:
    Top: label “top” OR upper clothing; include “scarf” optionally
    Bottom: “pants” OR “skirt” OR “belt”
    Outerwear: if scarf/coat not explicit, infer from overlap + CLIP classification on upper region: "jacket/coat" vs "shirt"
    Shoes: not explicit; infer from bottom-most region around “feet” + CLIP classification "shoes" vs "pants hem"
    Accessories: bag/hat/glasses/jewelry/scarf/belt
  - Return masks and cropped RGBA images with transparent background for each bucket.

Face blur:
- If mobile does it: accept.
- Backend MUST still run a “safety blur pass” (fast) on any detected faces in the stored crop, to ensure privacy.
- Store only blurred/cropped images (never store raw full scene in MVP).

ATTRIBUTE EXTRACTION — RETURN THIS JSON SCHEMA
{
  "colors": [{"hex":"#RRGGBB","pct":0.0-1.0}, ...],
  "pattern": {"type":"solid|patterned","confidence":0-1},
  "formality": 0-100,
  "structure": 0-100,
  "minimalism": 0-100,
  "silhouette": "slim|regular|oversized|unknown",
  "notes": ["freeform short strings"]
}

AESTHETIC SUMMARY GENERATION (NO LARGE TEXT GEN REQUIRED)
Generate a 1-line summary deterministically from:
- top colors (e.g., “neutral tones” if low saturation)
- silhouette
- structure/formality/minimalism bins
Example:
“Relaxed neutral layering with minimalist structure.”

JOB ORCHESTRATION
- /v1/captures enqueues a job (Celery) with capture_id.
- Worker runs pipeline and updates DB.
- When done, worker triggers Poke message.

SECURITY & PRIVACY
- Do not store faces unblurred.
- Do not store full-scene frames; only reticle-centered crop after blur.
- Use signed URLs or authenticated access for image retrieval in dashboard.
- Rate limit capture endpoint (basic).

LOCAL DEV / RUN
Provide:
- docker-compose.yml with:
  - api
  - worker
  - postgres
  - redis
  - (optional) minio
- Make targets or scripts:
  - make dev
  - make test
  - make embed-products
  - make reindex
- Seed script to create demo user + demo products.

OUTPUT FORMAT REQUIREMENT
You must output the entire repository as:
- A tree listing
- Then for each file: a header line “FILE: path/to/file” and a fenced code block with full contents.
Do NOT omit files. Do NOT output pseudocode—write runnable code.

QUALITY BAR
- Code must be clean, typed, lintable.
- Add comments for tricky parts (DAT integration, embedding math, radar scaling).
- Include robust error handling and logging.
- Keep MVP realistic and shippable as a hackathon demo.

BEGIN NOW.
1) Propose the final architecture + repo tree.
2) Then emit full code for every file.
3) Include README and setup instructions.
