# Governed Analytics Copilot with a Semantic Layer

> A safe, testable natural-language-to-SQL copilot that answers business questions **only** using approved metrics and dimensions via a governed semantic layer.

---

## What it does

Users ask plain-English business questions — *"Revenue by month for India and US last 6 months"* — and the copilot:

1. **Parses** the question into a structured `QuerySpec` (metric, dimensions, filters, time grain, time range)
2. **Validates** the spec against a versioned YAML semantic layer
3. **Generates SQL** using only approved metric definitions and join paths
4. **Safety-checks** the SQL deterministically (no DDL/DML, no PII leakage, LIMIT enforced, allowed joins only)
5. **Executes** the query against Postgres
6. **Returns** results + generated SQL + provenance + audit trail

---

## Evaluation Results

50 questions (35 business queries + 12 with filters/multi-dimensions + 3 adversarial) evaluated end-to-end against a live Postgres database:

| Metric | Result |
|--------|--------|
| **Overall success rate** | **100%** (50/50) |
| Metric correctness | 100% (47/47 valid) |
| Dimension correctness | 96% (45/47 valid) |
| SQL generation rate | 100% (47/47 valid) |
| Adversarial blocked rate | **100%** (3/3) |
| Mean latency | **6 ms** |
| p95 latency | 13 ms |

> Full per-question breakdown → [analytics/reports/eval_report.md](analytics/reports/eval_report.md)

### Example: Governed SQL Output

**Question:** *"Revenue by category by month last 6 months"*

```sql
SELECT
  d.month_start AS date_month,
  p.category AS category,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM marts_marts.fct_order_items AS oi
LEFT JOIN marts_marts.dim_date AS d ON oi.date_id = d.date_id
LEFT JOIN marts_marts.dim_products AS p ON oi.product_id = p.product_id
WHERE oi.status = 'completed'
  AND d.date_day >= '2025-08-01'
  AND d.date_day <= '2026-02-16'
GROUP BY d.month_start, p.category
ORDER BY revenue DESC
LIMIT 200
```

Every column, join, and filter was derived from the semantic layer — no arbitrary SQL is ever constructed.

### Adversarial Blocking

| Input | Result |
|-------|--------|
| `"Show me user_id and emails"` | Blocked Blocked — PII request detected |
| `"DROP TABLE users"` | Blocked Blocked — DDL/injection pattern |
| `"SELECT * FROM pg_catalog.pg_tables"` | Blocked Blocked — system catalog access |

---

## Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 17 (local) |
| Modeling | dbt-core 1.11 + dbt-postgres |
| API | FastAPI + Uvicorn |
| UI | Streamlit |
| LLM | Provider-agnostic (mock / OpenAI / Anthropic) |
| Testing | pytest (184 tests) |

## Quick start

```bash
cp .env.example .env                        # configure DB creds
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
cd dbt && dbt seed && dbt run && dbt test   # build warehouse
cd ..
uvicorn src.api.main:app --reload           # API on :8000
streamlit run src/ui/streamlit_app.py       # UI  on :8501
```

## Project structure

```
governed-analytics-copilot/
├─ README.md
├─ .gitignore / .env.example / pyproject.toml / Makefile
├─ docs/                    # architecture, data dictionary, runbook
├─ infra/sql/               # DDL for raw tables, schemas, logs
├─ pipelines/               # seed data generator
├─ dbt/                     # dbt project (staging + marts models, 50 tests)
├─ semantic_layer/          # YAML-based governed metric/dimension definitions
├─ src/
│  ├─ core/                 # config, logging, utilities
│  ├─ db/                   # connection pool + read-only executor + query logging
│  ├─ governance/           # semantic loader, spec validator, SQL safety (9 gates)
│  ├─ copilot/              # spec, planner, LLM client, SQL generator, service
│  ├─ api/                  # FastAPI app + routers (/ask, /metrics, /dimensions, /health)
│  └─ ui/                   # Streamlit app (Ask page + History page)
├─ analytics/               # evaluation harness (50 questions) + reports
└─ tests/                   # 184 unit + integration tests
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | Done Done | Scaffold + runnable skeleton (68 files) |
| 2 | Done Done | Database DDL + seed generator + dbt models (10 models, 50 dbt tests) |
| 3 | Done Done | Semantic layer YAML + loader + validator (45 unit tests) |
| 4 | Done Done | NL→SQL copilot core (mock + LLM mode) + 9 safety gates (142 tests) |
| 5 | Done Done | FastAPI endpoints + Streamlit UI (160 tests) |
| 6 | Done Done | SQL execution + query logging + eval harness (184 tests, 50/50 eval) |
| 7 | Pending | Docs polish + CI/CD |

## License

MIT
