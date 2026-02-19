# Governed Analytics Copilot with a Semantic Layer

A natural-language-to-SQL copilot that answers business questions using only approved metrics and dimensions defined in a governed semantic layer. Every query is validated, safety-checked, and audit-logged before execution.

---

## How it works

1. **Parse** -- NL question becomes a structured `QuerySpec` (metric, dimensions, filters, time grain)
2. **Validate** -- spec is checked against the YAML semantic layer
3. **RBAC** -- role-based access control ensures the user can access the requested metric/dimensions
4. **Generate SQL** -- only approved metric expressions, join paths, and tables are used
5. **Safety-check** -- 9 deterministic gates inspect the SQL before execution
6. **Cost guard** -- query complexity is scored; expensive queries are blocked or warned
7. **Execute** -- read-only query against Postgres, results returned with full provenance
8. **Explain** -- if blocked, an explanation layer tells the user *why* and *how to fix it*
9. **Cache** -- repeated questions are served from an in-memory TTL cache
10. **Chart** -- results are auto-visualised (line / bar / pie / KPI card)
11. **Audit log** -- every request is recorded in `copilot_query_logs`

---

## Features

### Core pipeline
- NL-to-SQL via mock keyword planner or LLM (OpenAI / Anthropic)
- Semantic layer governance (metrics, dimensions, joins, security rules)
- 9-gate SQL safety checker
- Read-only Postgres execution with statement timeout
- Full audit trail

### Role-Based Access Control (RBAC)
Finance metrics are restricted to the finance team. Marketing metrics go to marketing. Analysts get full access. Roles are defined in the semantic model YAML:

```yaml
roles:
  finance:
    allowed_metrics: [revenue, aov, orders, items_sold]
    allowed_dimensions: [date, country, category, brand, order_status]
  marketing:
    allowed_metrics: [active_users, orders, revenue]
    allowed_dimensions: [date, country, device]
  analyst:
    allowed_metrics: "*"
    allowed_dimensions: "*"
  viewer:
    allowed_metrics: [revenue, orders]
    allowed_dimensions: [date, country]
```

Set `role=None` or omit to bypass RBAC (open mode).

### Query cost & performance guardrails
Every query is scored 0–100 based on join count, dimension count, missing time filters, CTEs, and LIMIT. Queries above the threshold are blocked to protect the database. Users get actionable warnings like *"add a time_range filter"* or *"reduce dimensions"*.

### Explanation layer
When a query is blocked, the copilot explains:
- **Why** it was blocked (in plain language)
- **How to fix** the question

Works in mock mode (template-based, no API key) or LLM mode (richer natural-language output).

### Query caching
Frequently asked questions are served from an in-memory TTL cache (5-minute default, 256 entries). Cache stats (hit rate, size) are shown in the sidebar. The cache is keyed on `(question, mode, execute)` — same question gets instant results.

### Chart auto-generation
Results are automatically visualised based on the query shape:
- **Line chart** — time-series (date dimension)
- **Bar chart** — categorical breakdowns (brand, category, country …)
- **Pie chart** — single dimension with ≤6 categories
- **KPI card** — single metric, no dimensions
- **Table** — fallback for complex results

### Natural-language metric suggestions
Type a partial term and get ranked suggestions from the catalog:
```
User types:  "revenue"
System suggests:
  → revenue          (metric, 98% match)
  → revenue growth   (if defined)
  → aov              (related)
```
Uses Levenshtein + Jaccard + prefix matching — no LLM call needed.

---

## Governance rules

The SQL safety layer enforces these rules on every generated query:

- Only `SELECT` statements allowed (no DDL/DML)
- No `SELECT *` -- explicit columns only
- Blocked schemas: `pg_catalog`, `information_schema`
- Blocked columns in SELECT: `user_id`, `order_id` (PII protection)
- Only tables listed in `allowed_tables` may appear
- `LIMIT` is mandatory and capped at 200 rows
- No dangerous keywords (`DROP`, `ALTER`, `TRUNCATE`, `INSERT`, `DELETE`, `GRANT`, ...)
- No inline comments (`--`) or block comments (`/*`)
- Input-level regex blocks SQL injection patterns and PII requests (emails, passwords, SSN, ...)

All rules are defined in [semantic_layer/semantic_model.yml](semantic_layer/semantic_model.yml) and enforced in `src/governance/sql_safety.py`.

Derived metrics (e.g., `conversion_proxy`) are defined in the semantic layer for documentation but are not directly queryable. The validator blocks them and suggests querying their component metrics instead.

---

## Quick start

```bash
# 1. Clone and configure
cp .env.example .env                          # set DB creds (POSTGRES_USER, etc.)

# 2. Start Postgres (or use an existing instance)
docker compose up -d

# 3. Create venv and install
python -m venv .venv
source .venv/bin/activate                     # Linux/macOS
# .venv\Scripts\activate                      # Windows PowerShell

pip install -r requirements.txt
# or: pip install -e ".[dev]"

# 4. Seed raw data, then build dbt models
python -m pipelines.seed.seed_data            # inserts ~10K rows into raw schema
cd dbt && dbt seed && dbt run && dbt test     # builds staging + marts (10 models, 50 tests)
cd ..

# 5. Run
uvicorn src.api.main:app --reload             # API on :8000
streamlit run src/ui/streamlit_app.py         # UI  on :8501
```

### Try these questions

```
Revenue by country last 6 months
Monthly orders last 6 months
Top 10 categories by items sold this quarter
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ask` | Full pipeline: question → spec → validate → RBAC → SQL → safety → cost → execute → chart |
| `POST` | `/ask/explain` | Dry-run: question → spec → validate (no SQL execution) |
| `GET` | `/ask/suggest?q=rev` | Metric & dimension typeahead suggestions |
| `GET` | `/ask/cache/stats` | Cache hit rate, size, TTL |
| `POST` | `/ask/cache/clear` | Flush the query cache |
| `GET` | `/catalog` | Full catalog: metrics, dimensions, allowed tables, max rows |
| `GET` | `/metrics` | List queryable metric names |
| `GET` | `/metrics/detail` | Detailed metric metadata |
| `GET` | `/dimensions` | List dimension names |
| `GET` | `/dimensions/detail` | Detailed dimension metadata |
| `GET` | `/health` | Health check |

---

## Schema naming: `marts_marts`

dbt generates schema names as `<profile_schema>_<model_schema>`. Our dbt profile targets a schema called `marts`, and the mart models also declare `schema: marts`, so the resulting Postgres schema is `marts_marts`. This is standard dbt behavior--not a bug. All table references in the semantic layer use the fully qualified name (e.g., `marts_marts.fct_orders`).

---

## Evaluation results

50 questions evaluated end-to-end against a live Postgres database: 47 valid business queries + 3 adversarial inputs.

| Metric | Result |
|--------|--------|
| **Overall success rate** | **100%** (50/50) |
| Metric correctness | 100% (47/47 valid) |
| Dimension correctness | 96% (45/47 valid) |
| SQL generation rate | 100% (47/47 valid) |
| Adversarial blocked rate | **100%** (3/3) |
| Mean latency | **6 ms** |
| p95 latency | 13 ms |

**Denominators:** 47 valid business questions are scored on metric/dimension/SQL correctness. The 3 adversarial questions are scored only on whether they were blocked. All 50 contribute to the overall success rate.

Full per-question breakdown: [analytics/reports/eval_report.md](analytics/reports/eval_report.md)

### Example governed SQL

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

### Adversarial blocking

| Input | Result |
|-------|--------|
| `"Show me user_id and emails"` | Blocked -- PII request detected at input level |
| `"DROP TABLE users"` | Blocked -- DDL/injection pattern detected |
| `"SELECT * FROM pg_catalog.pg_tables"` | Blocked -- system catalog access denied |

---

## Stack

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 |
| Modeling | dbt-core + dbt-postgres |
| API | FastAPI + Uvicorn |
| UI | Streamlit |
| LLM | Provider-agnostic (mock / OpenAI / Anthropic) |
| Governance | YAML semantic layer + RBAC + SQL safety + cost guardrails |
| Testing | pytest (232 unit + integration tests) |

## Project structure

```
governed-analytics-copilot/
├── .env.example / pyproject.toml / requirements.txt / Makefile
├── docker-compose.yml          Postgres container
├── infra/sql/                  DDL for raw tables, schemas, audit log
├── pipelines/seed/             seed data generator (~10K rows)
├── dbt/                        staging + marts models (10 models, 50 dbt tests)
├── semantic_layer/             YAML-governed metrics, dimensions, joins, security, RBAC roles
├── src/
│   ├── core/                   config, logging, utils
│   ├── db/                     connection pool, read-only executor, query log
│   ├── governance/
│   │   ├── semantic_loader.py  YAML parser → typed SemanticModel
│   │   ├── validator.py        spec validation (metrics, dims, joins)
│   │   ├── sql_safety.py       9-gate SQL safety checker
│   │   ├── rbac.py             role-based access control
│   │   └── cost_guard.py       query cost scoring & blocking
│   ├── copilot/
│   │   ├── planner.py          NL → QuerySpec (mock or LLM)
│   │   ├── sql_generator.py    QuerySpec → governed SQL
│   │   ├── service.py          end-to-end orchestrator
│   │   ├── explainer.py        human-readable error explanations
│   │   ├── cache.py            in-memory TTL query cache
│   │   ├── chart_generator.py  auto-chart type selection
│   │   ├── suggestions.py      fuzzy metric/dimension suggestions
│   │   ├── llm_client.py       LLM abstraction (mock/OpenAI/Anthropic)
│   │   └── spec.py             QuerySpec Pydantic model
│   ├── api/                    FastAPI (/ask, /catalog, /health, /suggest, /cache)
│   └── ui/                     Streamlit (Ask + History pages)
├── analytics/                  eval harness (50 questions) + reports
└── tests/                      232 unit + integration tests
```

## License

MIT
