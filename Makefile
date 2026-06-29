.PHONY: up down logs ingest test fmt

# Bring up Postgres + API + Web (builds images on first run).
up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api

# Force a re-ingest inside the running api container.
ingest:
	docker compose exec api python -m app.ingest.run_all

# Run backend unit tests (no DB / no OpenAI needed).
test:
	cd backend && PYTHONPATH=. OPENAI_API_KEY=test python -m pytest -q
