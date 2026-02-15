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
  - ensure `POKE_WEBHOOK_URL=https://poke.com/api/v1/inbound/api-message`.
  - If using Poke integrations: create an API key in Poke (Settings → Advanced) and add an Integration (Settings → Connections → Integrations → New) pointing to the same webhook endpoint.
- No open-web matches:
  - set `SERPAPI_API_KEY` in `.env`.
  - verify `WEB_SEARCH_ENABLED=true`.

## Poke MCP Server

The Poke MCP server exposes Aesthetica's fashion intelligence as MCP tools that Poke's AI agent can call via text messaging.

### Start the MCP server

**Via docker-compose (recommended):**
```bash
docker compose -f infra/docker-compose.yml up poke-mcp -d
```

**Standalone (local dev):**
```bash
cd services/poke-mcp
PYTHONPATH=../api:../ml python server.py
```

The server runs on `http://localhost:8787/mcp`.

### Connect to Poke

1. Authenticate: `npx poke login`
2. Start tunnel: `npx poke tunnel http://localhost:8787/mcp --name "Aesthetica Fashion AI"`
3. Wait for "Tools synced" message — your MCP tools are now available to Poke.

### Create a Recipe

1. Go to poke.com/kitchen
2. Create Recipe: "Aesthetica — AI Fashion Stylist"
3. Add the Aesthetica integration
4. Add onboarding message: "Send me a photo of your outfit and I'll analyze your style!"
5. Publish to get a shareable link (`poke.com/r/<code>`)

### Available MCP Tools

| Tool | Description |
|---|---|
| `analyze_outfit` | Analyze outfit image URL (persistent, `mode=fast|full`) |
| `find_similar_products` | Search local catalog + optional web results |
| `get_style_scores` | Recent style score history and trend deltas |
| `get_catalog_results` | Recent catalog analyses + concise product summaries |
| `get_style_recommendations` | Style-driven shopping query + recommendation list |
| `get_wardrobe_stats` | Aggregate scan and score statistics |
| `get_my_style` | Compact style-identity snapshot |
| `search_clothes` | Targeted shopping search |
| `build_outfit` | Occasion-based outfit planning with links |

All tools now return compact JSON payloads designed for LLM tool-use (instead of long prose blocks).

### Troubleshooting

- `poke tunnel` not connecting: ensure MCP server is running and port 8787 is open.
- "No user profile found": run `make seed` to create the demo user.
- Empty product results: run `make embed-products` to build FAISS indexes.

## Operational Commands

- Tail logs: `make logs`
- Reindex via API: `make reindex`
- Stop stack: `make down`
