"""
SQL Generator — turns a validated QuerySpec into a governed SQL SELECT string.

The generator reads metric expressions, dimension columns, join paths, and
security rules entirely from the semantic model.  It never invents its own
table references or expressions.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from src.copilot.spec import QuerySpec
from src.governance.semantic_loader import (
    load_semantic_model,
    SemanticModel,
    Metric,
    Dimension,
    JoinEdge,
)
from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Time-range resolution ────────────────────────────────

_RANGE_RE = re.compile(
    r"last\s+(\d+)\s+(days?|weeks?|months?|years?)",
    re.IGNORECASE,
)


def _resolve_time_range(time_range: str | None) -> tuple[date, date] | None:
    """Convert a natural-language time range to (start, end) inclusive dates.

    Returns None when time_range is empty or unparseable.
    """
    if not time_range:
        return None

    today = date.today()

    if time_range.lower().strip() in ("this month",):
        return (today.replace(day=1), today)

    if time_range.lower().strip() in ("this year",):
        return (today.replace(month=1, day=1), today)

    if time_range.lower().strip() in ("year to date", "ytd"):
        return (today.replace(month=1, day=1), today)

    m = _RANGE_RE.search(time_range)
    if not m:
        return None

    n = int(m.group(1))
    unit = m.group(2).lower().rstrip("s")

    if unit == "day":
        start = today - timedelta(days=n)
    elif unit == "week":
        start = today - timedelta(weeks=n)
    elif unit == "month":
        # Approximate: go back n months
        month = today.month - n
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start = today.replace(year=year, month=month, day=1)
    elif unit == "year":
        start = today.replace(year=today.year - n, month=1, day=1)
    else:
        return None

    return (start, today)


# ── SQL builder ──────────────────────────────────────────

def generate_sql(spec: QuerySpec, model: SemanticModel | None = None) -> str:
    """Build a governed SQL SELECT from a validated QuerySpec.

    The SQL uses ONLY tables, columns, and expressions from the semantic model.
    """
    if model is None:
        model = load_semantic_model()

    metric = model.metric(spec.metric)
    if metric is None:
        raise ValueError(f"Unknown metric '{spec.metric}'")

    # ── SELECT clause ────────────────────────────────
    select_parts: list[str] = []
    group_parts: list[str] = []

    for dim_name in spec.dimensions:
        dim = model.dimension(dim_name)
        if dim is None:
            continue

        if dim_name == "date" and spec.time_grain:
            grain_expr = dim.grain_expressions.get(spec.time_grain, dim.column)
            select_parts.append(f"{grain_expr} AS date_{spec.time_grain}")
            group_parts.append(grain_expr)
        else:
            select_parts.append(f"{dim.column} AS {dim.name}")
            group_parts.append(dim.column)

    # Metric expression is always last in SELECT
    select_parts.append(f"{metric.expression} AS {metric.name}")

    # ── FROM clause ──────────────────────────────────
    from_clause = f"{metric.base_table} AS {metric.alias}"

    # ── JOIN clauses ─────────────────────────────────
    joined_tables: set[str] = {metric.base_table}  # already in FROM
    join_clauses: list[str] = []

    # Collect all tables we need to reach
    needed_tables: set[str] = set()
    for dim_name in spec.dimensions:
        dim = model.dimension(dim_name)
        if dim and dim.table != metric.base_table:
            needed_tables.add(dim.table)

    # Also tables required by filters
    filter_keys = list(spec.filters.keys())
    for fk in filter_keys:
        dim = model.dimension(fk)
        if dim and dim.table != metric.base_table:
            needed_tables.add(dim.table)

    # Time range needs date dim
    if spec.time_range and "date" not in spec.dimensions:
        date_dim = model.dimension("date")
        if date_dim and date_dim.table != metric.base_table:
            needed_tables.add(date_dim.table)

    # BFS from base table to each needed table, accumulate join edges
    join_edges_used: list[JoinEdge] = []
    for tbl in needed_tables:
        if tbl in joined_tables:
            continue
        path = model.find_join_path(metric.base_table, tbl)
        if path is None:
            logger.warning("No join path from %s to %s — skipping", metric.base_table, tbl)
            continue
        for edge in path:
            if edge not in join_edges_used:
                join_edges_used.append(edge)

    # Build JOIN text
    for edge in join_edges_used:
        # Determine which side is already joined
        if edge.left in joined_tables and edge.right not in joined_tables:
            target = edge.right
            alias = edge.right_alias
        elif edge.right in joined_tables and edge.left not in joined_tables:
            target = edge.left
            alias = edge.left_alias
        else:
            # Both already joined or neither — skip
            if edge.left not in joined_tables and edge.right not in joined_tables:
                # Neither — pick left as already in FROM (first edge case)
                target = edge.right
                alias = edge.right_alias
            else:
                continue

        jtype = edge.join_type.upper()
        join_clauses.append(f"{jtype} JOIN {target} AS {alias} ON {edge.on}")
        joined_tables.add(target)

    # ── WHERE clause ─────────────────────────────────
    where_parts: list[str] = []

    # Metric-level filters (e.g. status = 'completed')
    for f in metric.filters:
        where_parts.append(f)

    # Dimension-value filters from spec
    for dim_name, values in spec.filters.items():
        dim = model.dimension(dim_name)
        if dim is None:
            continue
        if len(values) == 1:
            # Use = for single value (safe: values were validated)
            safe_val = values[0].replace("'", "''")
            where_parts.append(f"{dim.column} = '{safe_val}'")
        else:
            safe_vals = ", ".join(f"'{v.replace(chr(39), chr(39)+chr(39))}'" for v in values)
            where_parts.append(f"{dim.column} IN ({safe_vals})")

    # Time range filter
    date_range = _resolve_time_range(spec.time_range)
    if date_range:
        date_dim = model.dimension("date")
        if date_dim:
            start_str = date_range[0].isoformat()
            end_str = date_range[1].isoformat()
            col = date_dim.column  # e.g. d.date_day
            where_parts.append(f"{col} >= '{start_str}'")
            where_parts.append(f"{col} <= '{end_str}'")

    # ── Assemble ─────────────────────────────────────
    sql_lines: list[str] = []

    # CTE support for complex metrics (e.g. returning_customers)
    if metric.cte:
        sql_lines.append(f"WITH {metric.cte.strip()}")

    sql_lines.append("SELECT")
    sql_lines.append("  " + ",\n  ".join(select_parts))
    sql_lines.append(f"FROM {from_clause}")

    # If metric has a CTE, auto-join it to the base table
    if metric.cte:
        # Extract CTE name (first word of cte string)
        cte_name = metric.cte.strip().split()[0]
        join_clauses.insert(0, f"LEFT JOIN {cte_name} AS uo ON {metric.alias}.user_id = uo.user_id")

    for jc in join_clauses:
        sql_lines.append(jc)

    if where_parts:
        sql_lines.append("WHERE " + "\n  AND ".join(where_parts))

    if group_parts:
        sql_lines.append("GROUP BY " + ", ".join(group_parts))

    # ORDER BY the metric descending by default
    sql_lines.append(f"ORDER BY {metric.name} DESC")

    # LIMIT
    limit = min(spec.limit, model.security.max_rows)
    sql_lines.append(f"LIMIT {limit}")

    sql = "\n".join(sql_lines)
    logger.info("Generated SQL:\n%s", sql)
    return sql
