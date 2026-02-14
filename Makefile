COMPOSE=docker compose -f infra/docker-compose.yml

.PHONY: dev down logs test embed-products reindex migrate seed

dev:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f api worker

test:
	$(COMPOSE) run --rm api pytest -q

embed-products:
	$(COMPOSE) run --rm api python /app/services/ml/scripts/embed_products.py

reindex:
	$(COMPOSE) run --rm api curl -s -X POST http://api:8000/v1/internal/reindex-products -H "Authorization: Bearer dev"

migrate:
	$(COMPOSE) run --rm api alembic upgrade head

seed:
	$(COMPOSE) run --rm api python /app/services/api/app/scripts/seed_demo.py
