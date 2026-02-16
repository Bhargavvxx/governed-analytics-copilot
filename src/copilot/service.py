"""
Copilot service -- orchestrates plan -> validate -> generate -> safety -> execute -> log.

Full end-to-end pipeline.  When `execute=True` (default), the generated SQL is
run against Postgres in a READ ONLY transaction and the result rows are returned.
Every call is recorded in the `copilot_query_logs` audit table.
"""
from __future__ import annotations

import re
import time
from typing import Any

from src.copilot.spec import QuerySpec
from src.copilot.planner import plan
from src.copilot.sql_generator import generate_sql
from src.governance.validator import validate_spec
from src.governance.sql_safety import check_sql_safety
from src.governance.semantic_loader import load_semantic_model
from src.db.executor import execute_readonly
from src.db.query_log import ensure_log_table, log_query
from src.core.logging import get_logger

logger = get_logger(__name__)

# Ensure the log table exists at import time (idempotent CREATE IF NOT EXISTS)
try:
    ensure_log_table()
except Exception:
    logger.warning("Could not ensure query log table (DB may not be available)")

_INJECTION_RE = re.compile(
    r"\b(DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE|DELETE\s+FROM|INSERT\s+INTO|"
    r"UPDATE\s+\w+\s+SET|GRANT\s|REVOKE\s|CREATE\s+TABLE|"
    r"pg_catalog|information_schema|pg_tables|pg_roles|"
    r"SELECT\s+\*\s+FROM|UNION\s+SELECT|;\s*SELECT|"
    r"xp_cmdshell|EXEC\s|EXECUTE\s|COPY\s|\\\\!)\b",
    re.IGNORECASE,
)

_PII_RE = re.compile(
    r"\b(emails?|passwords?|phone\s*numbers?|ssn|social\s*security|"
    r"credit\s*card|address(?:es)?|salary|salaries|date\s*of\s*birth|dob)\b",
    re.IGNORECASE,
)


def _check_input_safety(question: str) -> list[str]:
    """Detect SQL injection / adversarial patterns in the raw question."""
    errors: list[str] = []
    if _INJECTION_RE.search(question):
        errors.append("Question contains potentially dangerous SQL patterns -- blocked.")
    if _PII_RE.search(question):
        errors.append("Question requests personally identifiable information -- blocked.")
    return errors


class CopilotResult:
    def __init__(
        self,
        spec: QuerySpec,
        sql: str,
        rows: list[dict[str, Any]],
        validation_errors: list[str],
        safety_errors: list[str],
        latency_ms: int = 0,
    ):
        self.spec = spec
        self.sql = sql
        self.rows = rows
        self.validation_errors = validation_errors
        self.safety_errors = safety_errors
        self.latency_ms = latency_ms

    @property
    def success(self) -> bool:
        return not self.validation_errors and not self.safety_errors


def ask(
    question: str,
    mode: str = "mock",
    execute: bool = True,
) -> CopilotResult:
    """End-to-end: question -> structured result.

    Parameters
    ----------
    question : str
        Natural-language business question.
    mode : str
        Planner mode -- "mock" (keyword), "openai", or "anthropic".
    execute : bool
        If True, run the generated SQL against Postgres.
        If False, return the SQL without executing (dry-run).
    """
    t0 = time.perf_counter()
    logger.info("Copilot.ask | question=%s | mode=%s | execute=%s", question, mode, execute)

    model = load_semantic_model()

    # 0. Input-level adversarial check (before planning)
    input_errors = _check_input_safety(question)
    if input_errors:
        latency = int((time.perf_counter() - t0) * 1000)
        dummy_spec = QuerySpec(metric="blocked", dimensions=[], filters={}, time_grain=None, time_range=None, limit=0)
        try:
            log_query(question=question, mode=mode, spec=dummy_spec.model_dump(), sql="",
                      row_count=0, validation_errors=input_errors, safety_errors=[], latency_ms=latency)
        except Exception:
            pass
        return CopilotResult(spec=dummy_spec, sql="", rows=[], validation_errors=input_errors, safety_errors=[], latency_ms=latency)

    # 1. Plan: NL -> QuerySpec
    spec = plan(question, mode=mode)

    # 2. Validate spec against semantic model
    v_errors = validate_spec(spec.model_dump(), model)

    # 3. Generate governed SQL
    sql = ""
    s_errors: list[str] = []
    rows: list[dict[str, Any]] = []

    if not v_errors:
        sql = generate_sql(spec, model)
        # 4. Safety-check the generated SQL
        s_errors = check_sql_safety(sql, model)

    # 5. Execute (only if no errors and execution requested)
    if not v_errors and not s_errors and sql and execute:
        try:
            rows = execute_readonly(sql)
        except Exception as exc:
            logger.exception("SQL execution failed")
            s_errors.append(f"Execution error: {exc}")

    latency = int((time.perf_counter() - t0) * 1000)

    # 6. Audit log (fire-and-forget -- never block the response)
    try:
        log_query(
            question=question,
            mode=mode,
            spec=spec.model_dump(),
            sql=sql,
            row_count=len(rows),
            validation_errors=v_errors,
            safety_errors=s_errors,
            latency_ms=latency,
        )
    except Exception:
        logger.warning("Audit log write failed -- continuing")

    return CopilotResult(
        spec=spec,
        sql=sql,
        rows=rows,
        validation_errors=v_errors,
        safety_errors=s_errors,
        latency_ms=latency,
    )
