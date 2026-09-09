# AI Proposal Workflow — dev convenience commands.
# Run `make help` (or just `make`) to list everything below.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := help

BACKEND_DIR  := backend
FRONTEND_DIR := web-app

VENV     := $(BACKEND_DIR)/venv
PY       := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
ALEMBIC  := $(VENV)/bin/alembic
PYTEST   := $(VENV)/bin/pytest

# Migration message for `make migration` — override like:
#   make migration m="add proposal status index"
m ?= auto

.PHONY: help \
	install backend-install frontend-install \
	dev backend-dev frontend-dev backend-run \
	test backend-test frontend-test \
	lint frontend-lint \
	migration migrate migrate-up migrate-down migrate-history migrate-current \
	seed db-reset \
	backend-shell \
	clean

help: ## Show this help
	@echo "AI Proposal Workflow — available commands:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## ---------------------------------------------------------------------------
## Install
## ---------------------------------------------------------------------------

install: backend-install frontend-install ## Install backend + frontend dependencies

backend-install: ## Install backend Python dependencies into backend/venv
	if [ ! -d "$(VENV)" ]; then \
		echo "Creating venv at $(VENV)..."; \
		python3 -m venv $(VENV); \
	fi
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt

frontend-install: ## Install frontend dependencies (npm ci)
	cd $(FRONTEND_DIR) && npm install

## ---------------------------------------------------------------------------
## Run
## ---------------------------------------------------------------------------

dev: ## Run backend + frontend dev servers together (Ctrl+C stops both)
	trap 'kill 0' EXIT INT TERM
	$(MAKE) backend-dev &
	$(MAKE) frontend-dev &
	wait

backend-dev: ## Run the FastAPI dev server with autoreload
	cd $(BACKEND_DIR) && ./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

backend-run: backend-dev ## Alias for backend-dev

frontend-dev: ## Run the Next.js dev server
	cd $(FRONTEND_DIR) && npm run dev

## ---------------------------------------------------------------------------
## Test & lint
## ---------------------------------------------------------------------------

test: backend-test ## Run all backend tests (pytest)

backend-test: ## Run backend tests (pytest -q)
	cd $(BACKEND_DIR) && ./venv/bin/pytest -q

frontend-test: ## Run frontend tests (placeholder — no test script defined yet)
	cd $(FRONTEND_DIR) && npm test

lint: frontend-lint ## Run frontend lint (no backend linter configured yet)

frontend-lint: ## Run eslint on web-app
	cd $(FRONTEND_DIR) && npm run lint

## ---------------------------------------------------------------------------
## Database & migrations (Alembic)
## ---------------------------------------------------------------------------

migration: ## Autogenerate a new Alembic migration — usage: make migration m="add x"
	cd $(BACKEND_DIR) && ./venv/bin/alembic revision --autogenerate -m "$(m)"

migrate: migrate-up ## Alias for migrate-up

migrate-up: ## Apply all pending migrations (alembic upgrade head)
	cd $(BACKEND_DIR) && ./venv/bin/alembic upgrade head

migrate-down: ## Roll back the last migration (alembic downgrade -1)
	cd $(BACKEND_DIR) && ./venv/bin/alembic downgrade -1

migrate-history: ## Show migration history
	cd $(BACKEND_DIR) && ./venv/bin/alembic history --verbose

migrate-current: ## Show the current migration revision
	cd $(BACKEND_DIR) && ./venv/bin/alembic current

## ---------------------------------------------------------------------------
## Seed data
## ---------------------------------------------------------------------------

seed: migrate-up ## Seed a few sample proposals via the intake service (idempotent)
	cd $(BACKEND_DIR) && ./venv/bin/python - <<-'SEEDPY'
	import asyncio
	from app.core.database import AsyncSessionLocal
	from app.schemas.intake import IntakePayload
	from app.services.intake_service import process_intake
	
	SAMPLES = [
	    dict(
	        timestamp="2026-01-01 09:00:00",
	        respondent_email="sales.rep@example.com",
	        client_name="Alice Johnson",
	        client_email="alice@acme.com",
	        company_name="Acme Corp",
	        date_of_call="2026-01-01",
	        salesperson_name="Bob Smith",
	        client_needs_summary="Acme needs an end-to-end automated CRM integration.",
	        project_scope="Design and deployment of a custom CRM connector with automated webhooks.",
	        goals_and_objectives="Reduce manual entry by 80% and sync customer records in real-time.",
	        recommended_services="CRM API setup, custom middleware, data migration, staff training.",
	        proposed_timeline="6 weeks from kickoff",
	        estimated_pricing="$$15,000 USD flat fee",
	    ),
	    dict(
	        timestamp="2026-01-02 10:30:00",
	        respondent_email="sales.rep2@example.com",
	        client_name="Marcus Lee",
	        client_email="marcus@northwind.io",
	        company_name="Northwind Logistics",
	        date_of_call="2026-01-02",
	        salesperson_name="Dana White",
	        client_needs_summary="Northwind needs a fleet-tracking dashboard for dispatchers.",
	        project_scope="Build a real-time fleet tracking dashboard with route history.",
	        goals_and_objectives="Cut dispatcher response time in half within one quarter.",
	        recommended_services="Dashboard UI, GPS ingestion pipeline, alerting, onboarding.",
	        proposed_timeline="10 weeks from kickoff",
	        estimated_pricing="$$32,000 USD flat fee",
	    ),
	    dict(
	        timestamp="2026-01-03 14:15:00",
	        respondent_email="sales.rep3@example.com",
	        client_name="Priya Nair",
	        client_email="priya@brightpath.org",
	        company_name="BrightPath Education",
	        date_of_call="2026-01-03",
	        salesperson_name="Bob Smith",
	        client_needs_summary="BrightPath needs a student progress reporting portal.",
	        project_scope="Design and build a reporting portal for teachers and parents.",
	        goals_and_objectives="Give parents weekly visibility into student progress.",
	        recommended_services="Reporting portal, role-based access, email digests.",
	        proposed_timeline="8 weeks from kickoff",
	        estimated_pricing="$$21,500 USD flat fee",
	    ),
	]
	
	async def main(): s = AsyncSessionLocal(); db = await s.__aenter__(); [print(f"{'created' if created else 'already existed'}: {proposal.company_name} ({proposal.id})") for raw in SAMPLES for proposal, created in [await process_intake(db, IntakePayload(**raw))]]; await s.__aexit__(None, None, None)
	
	asyncio.run(main())
	SEEDPY

db-reset: ## Danger: wipe the local SQLite dev DB and re-apply migrations
	rm -f $(BACKEND_DIR)/proposals_dev.db
	cd $(BACKEND_DIR) && ./venv/bin/alembic upgrade head

## ---------------------------------------------------------------------------
## Misc
## ---------------------------------------------------------------------------

backend-shell: ## Drop into a shell with the backend venv activated
	cd $(BACKEND_DIR) && exec bash --rcfile <(echo "source venv/bin/activate")

clean: ## Remove Python/pytest caches
	find $(BACKEND_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(BACKEND_DIR)/.pytest_cache
