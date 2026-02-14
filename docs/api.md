# API Spec (Human-Readable)

Base URL: `http://localhost:8000`

OpenAPI docs: `/docs`

## Auth

- `POST /v1/auth/login`
  - body: `{ "email": "...", "password": "..." }`
  - returns: `{ "access_token": "...", "token_type": "bearer" }`
- `GET /v1/auth/me`

## Capture

- `POST /v1/captures`
  - multipart field: `image`
  - returns: `{ "capture_id": "...", "status": "queued" }`
- `GET /v1/captures/{capture_id}`
- `GET /v1/users/{user_id}/captures?limit=...`

## Results

- `GET /v1/users/{user_id}/profile`
- `GET /v1/users/{user_id}/radar/history?days=...`
- `GET /v1/products/search?embedding_b64=...&garment_type=top`
- `GET /v1/products/search?capture_id=...&garment_type=top`
- `GET /v1/products/search?capture_id=...&garment_type=top&include_web=true`
  - `include_web=true` appends live web matches (SerpAPI provider) to catalog matches.

## Internal

- `POST /v1/internal/reindex-products` (`Authorization: Bearer dev`)
- `POST /v1/internal/recompute-radar` (`Authorization: Bearer dev`)

## Health

- `GET /healthz`
- `GET /readyz`

## Media

- `GET /v1/media?path=...&token=...`
  - token can also be passed as bearer header.
