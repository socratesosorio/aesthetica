COMPOSE=docker compose -f infra/docker-compose.yml
LENS_TEST_IMAGE?=apps/ui-aesthetica/public/images/outfit-1.png
LENS_TEST_API_BASE?=http://catalog-api:8000

.PHONY: dev down logs logs-catalog test test-lens-shopping embed-products reindex migrate seed ui ui-build ui-install

dev:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f api worker

logs-catalog:
	$(COMPOSE) logs -f catalog-api

test:
	$(COMPOSE) run --rm api pytest -q

test-lens-shopping:
	$(COMPOSE) run --rm api python /app/services/api/app/scripts/test_lens_shopping_pipeline.py --image $(LENS_TEST_IMAGE) --api-base $(LENS_TEST_API_BASE)

embed-products:
	$(COMPOSE) run --rm api python /app/services/ml/scripts/embed_products.py

reindex:
	$(COMPOSE) run --rm api curl -s -X POST http://api:8000/v1/internal/reindex-products -H "Authorization: Bearer dev"

migrate:
	$(COMPOSE) run --rm api sh -lc "cd /app/services/api && alembic upgrade head"

seed:
	$(COMPOSE) run --rm api python /app/services/api/app/scripts/seed_demo.py

ui-install:
	cd apps/ui-aesthetica && pnpm install

ui:
	cd apps/ui-aesthetica && pnpm install && pnpm dev

ui-build:
	cd apps/ui-aesthetica && pnpm install && pnpm build
