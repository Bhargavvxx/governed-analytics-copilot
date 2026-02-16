# Architecture

## High-level flow

```
User Question (NL)
       │
       ▼
┌─────────────┐
│   Planner   │  ← mock (rule-based) or LLM
└──────┬──────┘
       │  QuerySpec
       ▼
┌─────────────┐
│  Validator   │  ← checks spec against semantic_model.yml
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ SQL Generator│  ← builds SQL from approved definitions
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Safety Check │  ← deterministic: no DDL, no PII, limit, join paths
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Executor    │  ← read-only Postgres query
└──────┬──────┘
       │
       ▼
  Results + Audit
```

## Stack

| Layer        | Technology              |
|-------------|------------------------|
| Database     | PostgreSQL 16 (Docker)  |
| Modeling     | dbt-core + dbt-postgres |
| Data Quality | Great Expectations      |
| API          | FastAPI + Uvicorn       |
| UI           | Streamlit               |
| LLM          | Provider-agnostic (mock / OpenAI / Anthropic) |

## Key design decisions

1. **Semantic layer as YAML** — versioned, human-readable, the single source of truth.
2. **Deterministic safety checks before execution** — no SQL runs without passing all gates.
3. **Mock mode first** — the entire pipeline works without an API key.
4. **Audit trail** — every query is logged with its spec, SQL, result metadata, and latency.
