.PHONY: help up down seed dbt api ui test eval lint

SHELL := /bin/bash

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ───────────────────────────────────────
up: ## Start Postgres via Docker Compose
	docker compose up -d --wait

down: ## Stop Postgres
	docker compose down

reset-db: down ## Destroy volume and re-create database
	docker compose down -v
	docker compose up -d --wait

# ── Data pipeline ────────────────────────────────────────
seed: ## Generate and load seed data
	python -m pipelines.seed.seed_data

dbt: ## Run dbt models
	cd dbt && dbt run --profiles-dir .

dbt-test: ## Run dbt tests
	cd dbt && dbt test --profiles-dir .

# ── Application ──────────────────────────────────────────
api: ## Start FastAPI server
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

ui: ## Start Streamlit app
	streamlit run src/ui/streamlit_app.py --server.port 8501

# ── Quality & Testing ────────────────────────────────────
test: ## Run pytest
	pytest tests/ -v

lint: ## Run ruff linter
	ruff check src/ tests/

eval: ## Run NL→SQL evaluation harness
	python -m analytics.eval.run_eval
