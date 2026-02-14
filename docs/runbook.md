# Local Runbook

## First-Time Boot

1. `cp .env.example .env`
2. `make dev`
3. `make migrate`
4. `make seed`
5. `make embed-products`

## Smoke Test

1. Login via API:
   - POST `/v1/auth/login` with demo creds.
2. Upload sample capture to `/v1/captures`.
3. Verify worker logs capture transitions `queued -> processing -> done`.
4. Open dashboard at `http://localhost:5173`.

## Common Issues

- `readyz` false with DB:
  - ensure postgres container healthy.
- Empty retrieval results:
  - run `make embed-products` and check `data/faiss` files.
- No Poke messages:
  - set `POKE_API_KEY` in `.env`.
- No open-web matches:
  - set `SERPAPI_API_KEY` in `.env`.
  - verify `WEB_SEARCH_ENABLED=true`.

## Operational Commands

- Tail logs: `make logs`
- Reindex via API: `make reindex`
- Stop stack: `make down`
