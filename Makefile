COMPOSE=docker compose -f infra/docker-compose.yml

.PHONY: dev down logs logs-catalog test embed-products reindex migrate seed ui ui-build ui-install

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
