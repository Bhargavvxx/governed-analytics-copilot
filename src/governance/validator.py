"""
Validates a QuerySpec against the semantic layer.

Checks performed:
  1. Metric exists in the semantic model
  2. Metric is not a derived/abstract metric that can't be queried directly
  3. Every requested dimension exists
  4. Every filter key is a valid dimension name
  5. If 'date' dimension is used, the time_grain must be an allowed grain
  6. Every dimension table is reachable from the metric's base table via
     approved join paths
  7. Filter values are non-empty strings (basic sanity)
"""
from __future__ import annotations

from typing import Any

from src.governance.semantic_loader import load_semantic_model, SemanticModel


def validate_spec(spec: dict[str, Any], model: SemanticModel | None = None) -> list[str]:
    """Return a list of validation error messages (empty list = spec is valid).

    Parameters
    ----------
    spec : dict
        A dict representation of a QuerySpec with keys:
        metric, dimensions, filters, time_grain, time_range, limit
    model : SemanticModel, optional
        If None, loads the default semantic model from disk.
    """
    if model is None:
        model = load_semantic_model()

    errors: list[str] = []

    metric_name: str = spec.get("metric", "")
    if not metric_name:
        errors.append("No metric specified.")
        return errors  # nothing else to validate

    metric_def = model.metric(metric_name)
    if metric_def is None:
        errors.append(
            f"Unknown metric '{metric_name}'. "
            f"Allowed: {', '.join(model.get_metric_names())}"
        )
        return errors  # can't do further validation

    if metric_def.is_derived:
        errors.append(
            f"Metric '{metric_name}' is a derived/composite metric and cannot be queried directly. "
            f"Its components are: {', '.join(metric_def.components)}"
        )
        return errors

    requested_dims: list[str] = spec.get("dimensions") or []
    for dim_name in requested_dims:
        if model.dimension(dim_name) is None:
            errors.append(
                f"Unknown dimension '{dim_name}'. "
                f"Allowed: {', '.join(model.get_dimension_names())}"
            )

    filters: dict[str, list[str]] = spec.get("filters") or {}
    for filter_key in filters:
        if model.dimension(filter_key) is None:
            errors.append(
                f"Filter key '{filter_key}' is not a recognized dimension. "
                f"Allowed: {', '.join(model.get_dimension_names())}"
            )

    time_grain: str | None = spec.get("time_grain")
    if time_grain:
        date_dim = model.dimension("date")
        if date_dim and date_dim.grains:
            if time_grain not in date_dim.grains:
                errors.append(
                    f"Invalid time grain '{time_grain}'. "
                    f"Allowed grains for 'date': {', '.join(date_dim.grains)}"
                )

    # If we already have errors on basic naming, skip join-path checks
    if errors:
        return errors

    base_table = metric_def.base_table
    if base_table:
        # Collect all dimension tables needed
        needed_tables: set[str] = set()
        for dim_name in requested_dims:
            dim_def = model.dimension(dim_name)
            if dim_def and dim_def.table != base_table:
                needed_tables.add(dim_def.table)

        # Also add tables for filter dimensions not in requested_dims
        for filter_key in filters:
            dim_def = model.dimension(filter_key)
            if dim_def and dim_def.table != base_table:
                needed_tables.add(dim_def.table)

        # Check each needed table is reachable from the metric's base table
        reachable = model.tables_reachable_from(base_table)
        for tbl in needed_tables:
            if tbl not in reachable:
                errors.append(
                    f"Dimension table '{tbl}' is not reachable from metric base table "
                    f"'{base_table}' via approved join paths."
                )
            else:
                # Verify explicit join path exists (not just graph connectivity)
                path = model.find_join_path(base_table, tbl)
                if path is None:
                    errors.append(
                        f"No approved join path from '{base_table}' to '{tbl}'."
                    )

    for filter_key, values in filters.items():
        if not isinstance(values, list):
            errors.append(f"Filter '{filter_key}' values must be a list.")
        elif not values:
            errors.append(f"Filter '{filter_key}' has an empty value list.")
        else:
            for v in values:
                if not isinstance(v, str) or not v.strip():
                    errors.append(f"Filter '{filter_key}' has an invalid/empty value: {v!r}")

    limit = spec.get("limit", 200)
    max_rows = model.security.max_rows
    if isinstance(limit, int) and limit > max_rows:
        errors.append(
            f"Requested limit ({limit}) exceeds maximum allowed ({max_rows})."
        )

    return errors
