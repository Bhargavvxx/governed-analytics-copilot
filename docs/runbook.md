# Runbook

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Python 3.11+
- pip / uv (recommended)

## Quick start

```bash
# 1. Clone & enter the project
cd governed-analytics-copilot

# 2. Copy env file
cp .env.example .env

# 3. Start Postgres
docker compose up -d --wait

# 4. Create a virtual environment & install
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -e ".[dev]"

# 5. Seed data (Phase 2+)
python -m pipelines.seed.seed_data

# 6. Run dbt (Phase 2+)
cd dbt && dbt run --profiles-dir . && cd ..

# 7. Start API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 8. Start UI (new terminal)
streamlit run src/ui/streamlit_app.py --server.port 8501

# 9. Run tests
pytest tests/ -v
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Postgres not starting | Check Docker is running; `docker compose logs postgres` |
| dbt connection error | Ensure `.env` matches `profiles.yml`; Postgres must be running |
| API import errors | Ensure you installed with `pip install -e .` from project root |
