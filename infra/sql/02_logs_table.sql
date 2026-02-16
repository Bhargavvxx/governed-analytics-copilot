-- 02_logs_table.sql
-- Audit log for every copilot query.

CREATE TABLE IF NOT EXISTS marts.copilot_query_logs (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    question        TEXT NOT NULL,
    parsed_spec_json JSONB,
    sql_text        TEXT,
    success         BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms      INT,
    row_count       INT,
    error           TEXT
);
