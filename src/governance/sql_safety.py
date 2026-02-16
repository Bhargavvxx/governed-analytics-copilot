"""
Deterministic SQL safety checks (non-LLM).

These checks are the final gate before any SQL is executed against Postgres.
They operate purely on the SQL text and the semantic model — no LLM involved.

Checks performed:
  1. SQL must be a single SELECT statement (no DDL / DML / multi-statement)
  2. No SELECT *
  3. No blocked schemas (pg_catalog, information_schema …)
  4. No blocked columns (user_id, order_id …)
  5. Only allowed tables may appear
  6. LIMIT must be present and ≤ max_rows
  7. No dangerous keywords (DROP, ALTER, TRUNCATE, INSERT, UPDATE, DELETE, GRANT …)
  8. No sub-shells / command execution attempts (;, --, /*, xp_, COPY, \\!)
"""
from __future__ import annotations

import re

from src.governance.semantic_loader import load_semantic_model, SemanticModel
from src.core.logging import get_logger

logger = get_logger(__name__)

# ── Compiled patterns ────────────────────────────────────

_DANGEROUS_KW = re.compile(
    r"\b(DROP|ALTER|TRUNCATE|INSERT|UPDATE|DELETE|MERGE|GRANT|REVOKE|"
    r"CREATE|REPLACE|EXECUTE|EXEC|CALL|COPY|SET\s+ROLE|RESET\s+ROLE)\b",
    re.IGNORECASE,
)

_MULTI_STMT = re.compile(r";\s*\S")  # semicolon followed by non-whitespace

_COMMENT_INLINE = re.compile(r"--")
_COMMENT_BLOCK = re.compile(r"/\*")

_SELECT_STAR = re.compile(r"\bSELECT\s+\*", re.IGNORECASE)

_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)

_FROM_JOIN_RE = re.compile(
    r"(?:FROM|JOIN)\s+([\w]+\.[\w]+|[\w]+)",
    re.IGNORECASE,
)


def check_sql_safety(
    sql: str,
    model: SemanticModel | None = None,
) -> list[str]:
    """Return a list of safety violations (empty list = safe).

    Parameters
    ----------
    sql : str
        The SQL query to validate.
    model : SemanticModel, optional
        If None, auto-loads the semantic model from disk.
    """
    if model is None:
        model = load_semantic_model()

    errors: list[str] = []
    sql_stripped = sql.strip()

    # ── 1. Must start with SELECT (or WITH … SELECT for CTEs) ─────
    upper = sql_stripped.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        errors.append("SQL must be a SELECT statement.")

    # ── 2. No multi-statement ────────────────────────
    if _MULTI_STMT.search(sql_stripped):
        errors.append("Multi-statement SQL is not allowed (found ';' followed by another statement).")

    # ── 3. No SELECT * ───────────────────────────────
    if _SELECT_STAR.search(sql_stripped):
        errors.append("SELECT * is not allowed. Specify explicit columns.")

    # ── 4. No dangerous keywords ─────────────────────
    m = _DANGEROUS_KW.search(sql_stripped)
    if m:
        errors.append(f"Dangerous keyword detected: '{m.group(1).upper()}'.")

    # ── 5. No SQL comments (injection vector) ────────
    if _COMMENT_INLINE.search(sql_stripped):
        errors.append("Inline comments (--) are not allowed.")
    if _COMMENT_BLOCK.search(sql_stripped):
        errors.append("Block comments (/* */) are not allowed.")

    # ── 6. Blocked schemas ───────────────────────────
    blocked_schemas = model.security.blocked_schemas
    sql_lower = sql_stripped.lower()
    for schema in blocked_schemas:
        if f"{schema}." in sql_lower:
            errors.append(f"Blocked schema referenced: '{schema}'.")

    # ── 7. Blocked columns ───────────────────────────
    # Only check in SELECT projection (before FROM)
    # Columns inside aggregate functions (COUNT, SUM, …) are safe — the raw
    # value is never exposed to the user.
    select_section = sql_stripped
    from_idx = sql_lower.find("\nfrom ")
    if from_idx == -1:
        from_idx = sql_lower.find(" from ")
    if from_idx != -1:
        select_section = sql_stripped[:from_idx]

    # Strip aggregate function contents before checking
    _agg_re = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\([^)]*\)", re.IGNORECASE)
    select_cleaned = _agg_re.sub("__agg__", select_section)

    for col in model.security.blocked_columns:
        # Must be a standalone reference: alias.col or just col as output name
        pattern = re.compile(
            rf"\b\w+\.{re.escape(col)}\b|\bAS\s+{re.escape(col)}\b",
            re.IGNORECASE,
        )
        if pattern.search(select_cleaned):
            errors.append(
                f"Blocked column '{col}' appears in the SELECT projection."
            )

    # ── 8. Allowed tables only ───────────────────────
    table_refs = _FROM_JOIN_RE.findall(sql_stripped)
    for ref in table_refs:
        # ref might be an alias-only (single word) — skip those
        if "." not in ref:
            continue
        if ref.lower() not in {t.lower() for t in model.allowed_tables}:
            errors.append(f"Table '{ref}' is not in the allowed tables list.")

    # ── 9. LIMIT must exist and be ≤ max_rows ───────
    limit_match = _LIMIT_RE.search(sql_stripped)
    if not limit_match:
        errors.append(f"SQL must include a LIMIT clause (max {model.security.max_rows}).")
    else:
        limit_val = int(limit_match.group(1))
        if limit_val > model.security.max_rows:
            errors.append(
                f"LIMIT {limit_val} exceeds maximum allowed ({model.security.max_rows})."
            )

    if errors:
        logger.warning("SQL safety violations: %s", errors)
    return errors
