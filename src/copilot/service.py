"""
Copilot service -- orchestrates plan -> validate -> generate -> safety -> execute -> log.

Full end-to-end pipeline.  When `execute=True` (default), the generated SQL is
run against Postgres in a READ ONLY transaction and the result rows are returned.
Every call is recorded in the `copilot_query_logs` audit table.

Enhanced with:
  - Role-based access control (RBAC)
  - Query cost & performance guardrails
  - LLM-based explanation layer
  - Query caching
  - Chart auto-generation
"""
from __future__ import annotations

import re
import time
from typing import Any

from src.copilot.spec import QuerySpec
from src.copilot.planner import plan
from src.copilot.sql_generator import generate_sql
from src.copilot.cache import get_cache
from src.copilot.explainer import explain_errors
from src.copilot.chart_generator import suggest_chart, ChartSpec
from src.governance.validator import validate_spec
from src.governance.sql_safety import check_sql_safety
from src.governance.rbac import check_rbac
from src.governance.cost_guard import estimate_query_cost, block_if_too_expensive, CostEstimate
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
        rbac_errors: list[str] | None = None,
        cost_warnings: list[str] | None = None,
        cost_score: int = 0,
        explanation: str = "",
        chart: ChartSpec | None = None,
        cached: bool = False,
    ):
        self.spec = spec
        self.sql = sql
        self.rows = rows
        self.validation_errors = validation_errors
        self.safety_errors = safety_errors
        self.latency_ms = latency_ms
        self.rbac_errors = rbac_errors or []
        self.cost_warnings = cost_warnings or []
        self.cost_score = cost_score
        self.explanation = explanation
        self.chart = chart
        self.cached = cached

    @property
    def success(self) -> bool:
        return (
            not self.validation_errors
            and not self.safety_errors
            and not self.rbac_errors
        )


def ask(
    question: str,
    mode: str = "mock",
    execute: bool = True,
    role: str | None = None,
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
    role : str | None
        Optional RBAC role (e.g. "finance", "marketing").
        If None, RBAC is not enforced.
    """
    t0 = time.perf_counter()
    logger.info("Copilot.ask | question=%s | mode=%s | execute=%s | role=%s",
                question, mode, execute, role)

    # ── Check cache first ───────────────────────────────
    cache = get_cache()
    cached_result = cache.get(question, mode, execute)
    if cached_result is not None:
        logger.info("Cache HIT for question=%s", question[:60])
        cached_result.cached = True
        cached_result.latency_ms = int((time.perf_counter() - t0) * 1000)
        return cached_result

    model = load_semantic_model()

    # 0. Input-level adversarial check (before planning)
    input_errors = _check_input_safety(question)
    if input_errors:
        latency = int((time.perf_counter() - t0) * 1000)
        dummy_spec = QuerySpec(metric="blocked", dimensions=[], filters={}, time_grain=None, time_range=None, limit=0)
        explanation = explain_errors(question, input_errors, [], mode=mode)
        try:
            log_query(question=question, mode=mode, spec=dummy_spec.model_dump(), sql="",
                      row_count=0, validation_errors=input_errors, safety_errors=[], latency_ms=latency)
        except Exception:
            pass
        return CopilotResult(
            spec=dummy_spec, sql="", rows=[],
            validation_errors=input_errors, safety_errors=[],
            latency_ms=latency, explanation=explanation,
        )

    # 1. Plan: NL -> QuerySpec
    spec = plan(question, mode=mode)

    # 1.5 RBAC check
    rbac_errors: list[str] = []
    if role:
        rbac_errors = check_rbac(role, spec.metric, spec.dimensions, model.roles)

    # 2. Validate spec against semantic model
    v_errors = validate_spec(spec.model_dump(), model)

    # 3. Generate governed SQL
    sql = ""
    s_errors: list[str] = []
    rows: list[dict[str, Any]] = []
    cost_warnings: list[str] = []
    cost_score = 0
    chart: ChartSpec | None = None

    if not v_errors and not rbac_errors:
        sql = generate_sql(spec, model)
        # 4. Safety-check the generated SQL
        s_errors = check_sql_safety(sql, model)

        # 4.5 Cost guardrails
        if not s_errors:
            cost_est = estimate_query_cost(spec.model_dump(), sql)
            cost_warnings = cost_est.warnings or []
            cost_score = cost_est.estimated_score
            blocking = block_if_too_expensive(cost_est)
            if blocking:
                s_errors.extend(blocking)

    # 5. Execute (only if no errors and execution requested)
    if not v_errors and not s_errors and not rbac_errors and sql and execute:
        try:
            rows = execute_readonly(sql)
        except Exception as exc:
            logger.exception("SQL execution failed")
            s_errors.append(f"Execution error: {exc}")

    # 5.5 Chart auto-generation
    if rows and not v_errors and not s_errors and not rbac_errors:
        try:
            chart = suggest_chart(spec.model_dump(), rows, spec.metric)
        except Exception:
            logger.warning("Chart generation failed -- continuing without chart")

    latency = int((time.perf_counter() - t0) * 1000)

    # 5.6 Explanation layer
    all_errors_exist = bool(v_errors or s_errors or rbac_errors)
    explanation = ""
    if all_errors_exist:
        explanation = explain_errors(
            question, v_errors, s_errors,
            cost_warnings=cost_warnings, rbac_errors=rbac_errors,
            mode=mode,
        )

    # 6. Audit log (fire-and-forget -- never block the response)
    try:
        log_query(
            question=question,
            mode=mode,
            spec=spec.model_dump(),
            sql=sql,
            row_count=len(rows),
            validation_errors=v_errors + rbac_errors,
            safety_errors=s_errors,
            latency_ms=latency,
        )
    except Exception:
        logger.warning("Audit log write failed -- continuing")

    result = CopilotResult(
        spec=spec,
        sql=sql,
        rows=rows,
        validation_errors=v_errors,
        safety_errors=s_errors,
        latency_ms=latency,
        rbac_errors=rbac_errors,
        cost_warnings=cost_warnings,
        cost_score=cost_score,
        explanation=explanation,
        chart=chart,
    )

    # ── Store in cache (only successful results) ────────
    if result.success and rows:
        cache.put(question, mode, execute, result)

    return result
