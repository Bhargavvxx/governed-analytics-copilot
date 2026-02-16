"""
Planner — converts a natural-language question into a QuerySpec.

Two modes:
  mock     → deterministic keyword extraction (no API key needed, great for tests)
  openai / anthropic → LLM-backed parsing via llm_client
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.copilot.spec import QuerySpec
from src.governance.semantic_loader import load_semantic_model, SemanticModel
from src.core.logging import get_logger

logger = get_logger(__name__)

# ── Keyword maps for mock mode ───────────────────────────

_METRIC_KEYWORDS: dict[str, list[str]] = {
    "revenue":              ["revenue", "sales", "money", "income", "earned"],
    "orders":               ["orders", "order count", "number of orders", "how many orders"],
    "aov":                  ["aov", "average order value", "avg order"],
    "items_sold":           ["items sold", "items", "quantity", "units sold", "units"],
    "returning_customers":  ["returning", "repeat", "loyal"],
    "active_users":         ["active users", "active", "active sessions", "dau", "mau"],
}

_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "date":         ["by date", "by day", "by week", "by month", "over time", "trend", "daily", "weekly", "monthly"],
    "country":      ["by country", "per country", "countries", "country"],
    "device":       ["by device", "per device", "devices", "device"],
    "category":     ["by category", "per category", "categories", "category"],
    "brand":        ["by brand", "per brand", "brands", "brand"],
    "order_status": ["by status", "per status", "order status"],
}

_GRAIN_KEYWORDS: dict[str, list[str]] = {
    "day":   ["daily", "by day", "per day", "each day"],
    "week":  ["weekly", "by week", "per week", "each week"],
    "month": ["monthly", "by month", "per month", "each month"],
}

_TIME_RANGE_PATTERNS: list[tuple[str, str]] = [
    # (regex pattern, normalised label)
    (r"last\s+(\d+)\s+days?",   "last {n} days"),
    (r"last\s+(\d+)\s+weeks?",  "last {n} weeks"),
    (r"last\s+(\d+)\s+months?", "last {n} months"),
    (r"last\s+(\d+)\s+years?",  "last {n} years"),
    (r"this\s+month",           "this month"),
    (r"this\s+year",            "this year"),
    (r"last\s+month",           "last 1 months"),
    (r"last\s+year",            "last 1 years"),
    (r"ytd|year\s*to\s*date",   "year to date"),
]

# ── Filter extraction helpers ────────────────────────────

# "in US", "in India", "for US", "where country is US"
_FILTER_COUNTRY_RE = re.compile(
    r"(?:in|for|where\s+country\s+(?:is|=))\s+([A-Z]{2}(?:\s*,\s*[A-Z]{2})*)",
    re.IGNORECASE,
)

_FILTER_CATEGORY_RE = re.compile(
    r"(?:category|categories)\s+(?:is|=|in)\s+['\"]?(\w[\w\s,]+)['\"]?",
    re.IGNORECASE,
)

_FILTER_BRAND_RE = re.compile(
    r"(?:brand|brands)\s+(?:is|=|in)\s+['\"]?(\w[\w\s,]+)['\"]?",
    re.IGNORECASE,
)


def _extract_filters(question: str) -> dict[str, list[str]]:
    """Best-effort extraction of dimension-filter values from NL."""
    filters: dict[str, list[str]] = {}

    m = _FILTER_COUNTRY_RE.search(question)
    if m:
        vals = [v.strip() for v in m.group(1).split(",") if v.strip()]
        if vals:
            filters["country"] = vals

    m = _FILTER_CATEGORY_RE.search(question)
    if m:
        vals = [v.strip() for v in m.group(1).split(",") if v.strip()]
        if vals:
            filters["category"] = vals

    m = _FILTER_BRAND_RE.search(question)
    if m:
        vals = [v.strip() for v in m.group(1).split(",") if v.strip()]
        if vals:
            filters["brand"] = vals

    return filters


# ── Mock planner ─────────────────────────────────────────

def _plan_mock(question: str, model: SemanticModel) -> QuerySpec:
    """Deterministic keyword-based NL→QuerySpec parser."""
    q = question.lower().strip()

    # 1. Detect metric (first match wins; most specific keywords first)
    metric = "revenue"  # fallback
    best_pos = len(q) + 1
    for name, keywords in _METRIC_KEYWORDS.items():
        for kw in keywords:
            pos = q.find(kw)
            if pos != -1 and pos < best_pos:
                metric = name
                best_pos = pos

    # 2. Detect dimensions
    dims: list[str] = []
    for name, keywords in _DIMENSION_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                if name not in dims:
                    dims.append(name)
                break

    # 3. Detect time grain
    grain: str | None = None
    for g, keywords in _GRAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                grain = g
                break
        if grain:
            break

    # If date dimension detected but no explicit grain, default to month
    if "date" in dims and grain is None:
        grain = "month"

    # 4. Detect time range
    time_range: str | None = None
    for pattern, template in _TIME_RANGE_PATTERNS:
        m = re.search(pattern, q)
        if m:
            if "{n}" in template:
                time_range = template.replace("{n}", m.group(1))
            else:
                time_range = template
            break

    # 5. Extract filters
    filters = _extract_filters(question)

    # 6. Extract limit (e.g. "top 10", "limit 50")
    limit = model.security.max_rows
    limit_match = re.search(r"(?:top|limit)\s+(\d+)", q)
    if limit_match:
        limit = min(int(limit_match.group(1)), model.security.max_rows)

    return QuerySpec(
        metric=metric,
        dimensions=dims,
        filters=filters,
        time_grain=grain,
        time_range=time_range,
        limit=limit,
    )


# ── LLM planner ─────────────────────────────────────────

_LLM_SYSTEM_PROMPT = """\
You are a semantic-layer query planner. Given a natural-language business question, \
extract a JSON object with these exact fields:

  metric       : string  — one of: {metrics}
  dimensions   : list[string] — zero or more of: {dimensions}
  filters      : dict[string, list[string]] — dimension name → allowed values
  time_grain   : string | null — one of: day, week, month (or null)
  time_range   : string | null — e.g. "last 6 months" (or null)
  limit        : int — max rows, default {max_rows}, max {max_rows}

Respond ONLY with valid JSON. No markdown, no explanation."""


def _build_llm_prompt(question: str, model: SemanticModel) -> str:
    system = _LLM_SYSTEM_PROMPT.format(
        metrics=", ".join(model.get_metric_names()),
        dimensions=", ".join(model.get_dimension_names()),
        max_rows=model.security.max_rows,
    )
    return f"{system}\n\nQuestion: {question}\n\nJSON:"


def _parse_llm_response(text: str, model: SemanticModel) -> QuerySpec:
    """Parse the LLM's JSON response into a QuerySpec, with fallback."""
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned invalid JSON, falling back to mock: %s", exc)
        return _plan_mock("", model)

    # Clamp limit
    max_rows = model.security.max_rows
    limit = min(int(data.get("limit", max_rows)), max_rows)

    return QuerySpec(
        metric=data.get("metric", "revenue"),
        dimensions=data.get("dimensions", []),
        filters=data.get("filters", {}),
        time_grain=data.get("time_grain"),
        time_range=data.get("time_range"),
        limit=limit,
    )


def _plan_llm(question: str, model: SemanticModel) -> QuerySpec:
    """Call the LLM and parse its response into a QuerySpec."""
    from src.copilot.llm_client import call_llm

    prompt = _build_llm_prompt(question, model)
    response = call_llm(prompt)
    return _parse_llm_response(response, model)


# ── Public API ───────────────────────────────────────────

def plan(question: str, mode: str = "mock") -> QuerySpec:
    """Parse *question* into a QuerySpec.

    Modes
    -----
    mock              — rule-based keyword extraction (no API key needed)
    openai / anthropic — LLM-backed parsing via llm_client
    """
    model = load_semantic_model()

    if mode == "mock":
        spec = _plan_mock(question, model)
    else:
        spec = _plan_llm(question, model)

    logger.info("Planner[%s] -> %s", mode, spec.model_dump_json(indent=None))
    return spec
