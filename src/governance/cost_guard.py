"""
Query cost & performance guardrails.

Prevents expensive queries from being executed by estimating query complexity
based on heuristics (number of joins, dimensions, lack of time-range filters,
etc.) and enforcing configurable thresholds.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Thresholds ──────────────────────────────────────────

MAX_JOINS = 4
MAX_DIMENSIONS = 5
MAX_FILTERS = 6
REQUIRE_TIME_RANGE = True  # warn if no time_range on date-dimension queries
MAX_LIMIT = 200  # hard cap


@dataclass
class CostEstimate:
    """Estimated query cost breakdown."""
    join_count: int = 0
    dimension_count: int = 0
    filter_count: int = 0
    has_time_range: bool = False
    has_cte: bool = False
    estimated_score: int = 0  # 0-100, higher = more expensive
    warnings: list[str] | None = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def estimate_query_cost(
    spec: dict[str, Any],
    sql: str,
    *,
    max_joins: int = MAX_JOINS,
    max_dimensions: int = MAX_DIMENSIONS,
    max_filters: int = MAX_FILTERS,
    max_limit: int = MAX_LIMIT,
) -> CostEstimate:
    """Estimate the cost of a query and return warnings for expensive operations.

    Parameters
    ----------
    spec : dict
        The QuerySpec dictionary.
    sql : str
        The generated SQL string.
    max_joins, max_dimensions, max_filters, max_limit : int
        Configurable thresholds.

    Returns
    -------
    CostEstimate
        Breakdown with a numeric score and human-readable warnings.
    """
    warnings: list[str] = []
    score = 0

    # ── Dimension count ─────────────────────────────────
    dims = spec.get("dimensions", [])
    dim_count = len(dims)
    if dim_count > max_dimensions:
        warnings.append(
            f"Query uses {dim_count} dimensions (max recommended: {max_dimensions}). "
            f"Consider reducing breakdowns for faster results."
        )
    score += dim_count * 8

    # ── Join count ──────────────────────────────────────
    join_count = len(re.findall(r"\bJOIN\b", sql, re.IGNORECASE))
    if join_count > max_joins:
        warnings.append(
            f"Query requires {join_count} table joins (max recommended: {max_joins}). "
            f"This may be slow on large datasets."
        )
    score += join_count * 12

    # ── Filter count ────────────────────────────────────
    filters = spec.get("filters", {})
    filter_count = sum(len(v) if isinstance(v, list) else 1 for v in filters.values())
    if filter_count > max_filters:
        warnings.append(
            f"Query has {filter_count} filter values (max recommended: {max_filters})."
        )
    score += max(0, filter_count - 2) * 3

    # ── Time range guard ────────────────────────────────
    has_time_range = bool(spec.get("time_range"))
    if "date" in dims and not has_time_range:
        warnings.append(
            "Query groups by date but has no time_range filter. "
            "This may scan the entire table — consider adding a time range."
        )
        score += 20

    # ── CTE detection ───────────────────────────────────
    has_cte = sql.upper().lstrip().startswith("WITH")
    if has_cte:
        score += 15

    # ── LIMIT guard ─────────────────────────────────────
    limit = spec.get("limit", 200)
    if limit > max_limit:
        warnings.append(
            f"Requested limit ({limit}) exceeds performance cap ({max_limit})."
        )
        score += 10

    # Clamp score to 0–100
    score = min(score, 100)

    estimate = CostEstimate(
        join_count=join_count,
        dimension_count=dim_count,
        filter_count=filter_count,
        has_time_range=has_time_range,
        has_cte=has_cte,
        estimated_score=score,
        warnings=warnings,
    )

    if warnings:
        logger.warning("Cost guardrails triggered: score=%d warnings=%s", score, warnings)

    return estimate


def block_if_too_expensive(estimate: CostEstimate, threshold: int = 85) -> list[str]:
    """Return blocking errors if estimated cost exceeds the threshold.

    Parameters
    ----------
    estimate : CostEstimate
        Result from ``estimate_query_cost``.
    threshold : int
        Score at or above which the query is blocked.

    Returns
    -------
    list[str]
        Error messages if blocked, otherwise empty list.
    """
    if estimate.estimated_score >= threshold:
        return [
            f"Query estimated cost score is {estimate.estimated_score}/100 "
            f"(threshold: {threshold}). Query blocked to protect database performance. "
            f"Suggestions: reduce dimensions, add a time_range filter, or lower the LIMIT."
        ]
    return []
