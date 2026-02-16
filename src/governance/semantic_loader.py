"""
Loads, parses, and caches the semantic model YAML into strongly-typed objects.

The semantic model is the single source of truth for:
  - approved metrics  (expressions, base tables, required joins)
  - allowed dimensions (columns, tables, grains)
  - valid join paths  (left/right tables, conditions)
  - security rules    (blocked columns, blocked schemas, max rows)
  - allowed tables
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml

_SEMANTIC_PATH = Path(__file__).resolve().parents[2] / "semantic_layer" / "semantic_model.yml"


# ── Typed domain objects ─────────────────────────────────

@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    expression: str | None
    base_table: str | None
    alias: str | None
    filters: list[str] = field(default_factory=list)
    requires_joins: list[str] = field(default_factory=list)
    is_derived: bool = False
    is_complex: bool = False
    components: list[str] = field(default_factory=list)
    cte: str | None = None


@dataclass(frozen=True)
class Dimension:
    name: str
    column: str
    table: str
    alias: str
    grains: list[str] = field(default_factory=list)
    grain_expressions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class JoinEdge:
    left: str
    left_alias: str
    right: str
    right_alias: str
    on: str
    join_type: str  # left | inner | right


@dataclass(frozen=True)
class SecurityRules:
    blocked_columns: list[str] = field(default_factory=list)
    blocked_schemas: list[str] = field(default_factory=list)
    read_only: bool = True
    max_rows: int = 200


@dataclass
class SemanticModel:
    """Fully parsed semantic layer."""

    version: int
    metrics: dict[str, Metric]          # keyed by name
    dimensions: dict[str, Dimension]    # keyed by name
    joins: list[JoinEdge]
    security: SecurityRules
    allowed_tables: set[str]

    # ── Convenience look-ups ─────────────────────────

    def metric(self, name: str) -> Metric | None:
        return self.metrics.get(name)

    def dimension(self, name: str) -> Dimension | None:
        return self.dimensions.get(name)

    def get_metric_names(self) -> list[str]:
        return list(self.metrics.keys())

    def get_dimension_names(self) -> list[str]:
        return list(self.dimensions.keys())

    def get_metrics_list(self) -> list[dict[str, Any]]:
        """Return metrics as a list of dicts (for API responses)."""
        result = []
        for m in self.metrics.values():
            result.append({
                "name": m.name,
                "description": m.description,
                "is_derived": m.is_derived,
            })
        return result

    def get_dimensions_list(self) -> list[dict[str, Any]]:
        """Return dimensions as a list of dicts (for API responses)."""
        result = []
        for d in self.dimensions.values():
            result.append({
                "name": d.name,
                "column": d.column,
                "grains": d.grains or [],
            })
        return result

    # ── Join graph helpers ───────────────────────────

    def find_join(self, left_table: str, right_table: str) -> JoinEdge | None:
        """Return the join edge connecting *left_table* → *right_table* (either direction)."""
        for j in self.joins:
            if j.left == left_table and j.right == right_table:
                return j
            if j.left == right_table and j.right == left_table:
                return j
        return None

    def tables_reachable_from(self, start: str) -> set[str]:
        """BFS from *start* table through the join graph; returns all reachable tables."""
        visited: set[str] = set()
        queue = [start]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for j in self.joins:
                if j.left == current and j.right not in visited:
                    queue.append(j.right)
                if j.right == current and j.left not in visited:
                    queue.append(j.left)
        return visited

    def find_join_path(self, from_table: str, to_table: str) -> list[JoinEdge] | None:
        """Return the shortest path of JoinEdges from *from_table* to *to_table*, or None."""
        if from_table == to_table:
            return []
        # BFS over join graph
        visited: set[str] = {from_table}
        queue: list[tuple[str, list[JoinEdge]]] = [(from_table, [])]
        while queue:
            current, path = queue.pop(0)
            for j in self.joins:
                if j.left == current and j.right not in visited:
                    new_path = path + [j]
                    if j.right == to_table:
                        return new_path
                    visited.add(j.right)
                    queue.append((j.right, new_path))
                elif j.right == current and j.left not in visited:
                    new_path = path + [j]
                    if j.left == to_table:
                        return new_path
                    visited.add(j.left)
                    queue.append((j.left, new_path))
        return None  # no path

    def alias_to_table(self) -> dict[str, str]:
        """Return a map of alias → fully-qualified table name."""
        mapping: dict[str, str] = {}
        for m in self.metrics.values():
            if m.alias and m.base_table:
                mapping[m.alias] = m.base_table
        for d in self.dimensions.values():
            if d.alias:
                mapping[d.alias] = d.table
        for j in self.joins:
            mapping[j.left_alias] = j.left
            mapping[j.right_alias] = j.right
        return mapping


# ── Parsing ──────────────────────────────────────────────

def _parse_metric(raw: dict[str, Any]) -> Metric:
    return Metric(
        name=raw["name"],
        description=raw.get("description", ""),
        expression=raw.get("expression"),
        base_table=raw.get("base_table"),
        alias=raw.get("alias"),
        filters=raw.get("filters") or [],
        requires_joins=raw.get("requires_joins") or [],
        is_derived=raw.get("is_derived", False),
        is_complex=raw.get("is_complex", False),
        components=raw.get("components") or [],
        cte=raw.get("cte"),
    )


def _parse_dimension(raw: dict[str, Any]) -> Dimension:
    return Dimension(
        name=raw["name"],
        column=raw["column"],
        table=raw["table"],
        alias=raw["alias"],
        grains=raw.get("grains") or [],
        grain_expressions=raw.get("grain_expressions") or {},
    )


def _parse_join(raw: dict[str, Any]) -> JoinEdge:
    return JoinEdge(
        left=raw["left"],
        left_alias=raw.get("left_alias", ""),
        right=raw["right"],
        right_alias=raw.get("right_alias", ""),
        on=raw["on"],
        join_type=raw.get("type", "left"),
    )


def _parse_security(raw: dict[str, Any] | None) -> SecurityRules:
    if not raw:
        return SecurityRules()
    return SecurityRules(
        blocked_columns=[c.lower() for c in raw.get("blocked_columns", [])],
        blocked_schemas=[s.lower() for s in raw.get("blocked_schemas", [])],
        read_only=raw.get("read_only", True),
        max_rows=raw.get("max_rows", 200),
    )


def _parse_model(raw_yaml: dict[str, Any]) -> SemanticModel:
    metrics = {m["name"]: _parse_metric(m) for m in raw_yaml.get("metrics", [])}
    dimensions = {d["name"]: _parse_dimension(d) for d in raw_yaml.get("dimensions", [])}
    joins = [_parse_join(j) for j in raw_yaml.get("joins", [])]
    security = _parse_security(raw_yaml.get("security"))
    allowed = set(raw_yaml.get("allowed_tables", []))
    return SemanticModel(
        version=raw_yaml.get("version", 1),
        metrics=metrics,
        dimensions=dimensions,
        joins=joins,
        security=security,
        allowed_tables=allowed,
    )


# ── Public API ───────────────────────────────────────────

@lru_cache
def load_semantic_model() -> SemanticModel:
    """Load and cache the semantic model from YAML."""
    with open(_SEMANTIC_PATH) as f:
        raw = yaml.safe_load(f)
    return _parse_model(raw)


def get_metric_names() -> list[str]:
    return load_semantic_model().get_metric_names()


def get_dimension_names() -> list[str]:
    return load_semantic_model().get_dimension_names()
