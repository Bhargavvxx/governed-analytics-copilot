"""
Auto-chart generation.

Given a CopilotResult with rows and a QuerySpec, determines the best
chart type and returns a chart specification that the UI can render.

Supported chart types:
  - bar       (categorical breakdowns: brand, category, country …)
  - line      (time-series with date dimension)
  - pie       (single-dimension, few categories)
  - metric    (single KPI number, no dimensions)
  - table     (fallback for complex or wide results)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)

# ── Chart types ─────────────────────────────────────────

CHART_BAR = "bar"
CHART_LINE = "line"
CHART_PIE = "pie"
CHART_METRIC = "metric"  # single KPI card
CHART_TABLE = "table"


@dataclass
class ChartSpec:
    """Describes how a set of result rows should be visualised."""
    chart_type: str
    title: str
    x_column: str | None = None
    y_column: str | None = None
    color_column: str | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    kpi_value: Any = None
    kpi_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "color_column": self.color_column,
            "kpi_value": self.kpi_value,
            "kpi_label": self.kpi_label,
            "row_count": len(self.rows),
        }


# ── Time-dimension detection ───────────────────────────

_TIME_COLUMNS = {"date_day", "date_week", "date_month", "week_start", "month_start"}


def _is_time_column(col: str) -> bool:
    """Heuristic: does this column name look like a time axis?"""
    return col.lower() in _TIME_COLUMNS or col.lower().startswith("date_")


# ── Chart selection logic ───────────────────────────────


def suggest_chart(
    spec_dict: dict[str, Any],
    rows: list[dict[str, Any]],
    metric_name: str,
) -> ChartSpec:
    """Choose the best chart type and build a ``ChartSpec``.

    Parameters
    ----------
    spec_dict : dict
        The QuerySpec as a dictionary.
    rows : list[dict]
        Tabular result rows.
    metric_name : str
        The primary metric name.

    Returns
    -------
    ChartSpec
        A chart specification for the UI to render.
    """
    dims: list[str] = spec_dict.get("dimensions", [])
    title = _build_title(metric_name, dims, spec_dict.get("time_range"))

    # No rows → empty table
    if not rows:
        return ChartSpec(chart_type=CHART_TABLE, title=title, rows=[])

    columns = list(rows[0].keys())

    # ── Single KPI (no dimensions) ──────────────────────
    if not dims and len(rows) == 1:
        value = rows[0].get(metric_name, list(rows[0].values())[-1])
        return ChartSpec(
            chart_type=CHART_METRIC,
            title=title,
            kpi_value=value,
            kpi_label=metric_name,
            rows=rows,
        )

    # ── Identify x-axis (first dimension column) ───────
    x_col = _find_x_column(columns, dims)
    y_col = metric_name if metric_name in columns else columns[-1]

    # ── Time-series → line chart ────────────────────────
    if x_col and _is_time_column(x_col):
        color = _find_color_column(columns, x_col, y_col) if len(dims) > 1 else None
        return ChartSpec(
            chart_type=CHART_LINE,
            title=title,
            x_column=x_col,
            y_column=y_col,
            color_column=color,
            rows=rows,
        )

    # ── Pie chart for ≤ 6 categories, single dimension ─
    if len(dims) == 1 and len(rows) <= 6:
        return ChartSpec(
            chart_type=CHART_PIE,
            title=title,
            x_column=x_col,
            y_column=y_col,
            rows=rows,
        )

    # ── Default: bar chart ──────────────────────────────
    color = _find_color_column(columns, x_col, y_col) if len(dims) > 1 else None
    return ChartSpec(
        chart_type=CHART_BAR,
        title=title,
        x_column=x_col,
        y_column=y_col,
        color_column=color,
        rows=rows,
    )


# ── Helpers ─────────────────────────────────────────────


def _build_title(metric: str, dims: list[str], time_range: str | None) -> str:
    """Build a descriptive chart title."""
    parts = [metric.replace("_", " ").title()]
    if dims:
        parts.append("by " + ", ".join(d.replace("_", " ").title() for d in dims))
    if time_range:
        parts.append(f"({time_range})")
    return " ".join(parts)


def _find_x_column(columns: list[str], dims: list[str]) -> str | None:
    """Pick the best x-axis column from the result set."""
    # Prefer time columns
    for col in columns:
        if _is_time_column(col):
            return col
    # Then the first dimension that appears in columns
    for dim in dims:
        for col in columns:
            if dim in col.lower():
                return col
    # Fallback to first non-metric column
    return columns[0] if len(columns) > 1 else None


def _find_color_column(columns: list[str], x_col: str | None, y_col: str | None) -> str | None:
    """Pick a color/group column (for stacked/grouped charts)."""
    for col in columns:
        if col != x_col and col != y_col:
            return col
    return None
