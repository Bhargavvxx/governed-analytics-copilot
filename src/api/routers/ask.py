"""POST /ask -- main copilot endpoint (enhanced with RBAC, caching, cost, charts, explanations)."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from src.copilot.service import ask as copilot_ask
from src.copilot.planner import plan as copilot_plan
from src.copilot.cache import get_cache
from src.copilot.suggestions import suggest
from src.governance.validator import validate_spec
from src.governance.semantic_loader import load_semantic_model
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()



class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Natural-language business question")
    mode: str = Field("mock", description="mock | openai | anthropic")
    execute: bool = Field(True, description="If true, run SQL against Postgres and return rows")
    role: str | None = Field(None, description="RBAC role (e.g. 'finance', 'marketing', 'analyst')")


class SpecResponse(BaseModel):
    metric: str
    dimensions: list[str]
    filters: dict
    time_grain: str | None
    time_range: str | None
    limit: int


class ChartResponse(BaseModel):
    chart_type: str
    title: str
    x_column: str | None = None
    y_column: str | None = None
    color_column: str | None = None
    kpi_value: str | None = None
    kpi_label: str | None = None
    row_count: int = 0


class AskResponse(BaseModel):
    question: str
    spec: SpecResponse
    sql: str
    rows: list[dict]
    validation_errors: list[str]
    safety_errors: list[str]
    rbac_errors: list[str]
    cost_warnings: list[str]
    cost_score: int
    explanation: str
    chart: ChartResponse | None
    success: bool
    latency_ms: int
    cached: bool


class ExplainResponse(BaseModel):
    question: str
    spec: SpecResponse
    validation_errors: list[str]
    is_valid: bool


class SuggestionItem(BaseModel):
    name: str
    kind: str
    description: str
    score: float
    is_derived: bool = False


class SuggestResponse(BaseModel):
    query: str
    suggestions: list[SuggestionItem]


class CacheStatsResponse(BaseModel):
    size: int
    max_size: int
    ttl_seconds: float
    hits: int
    misses: int
    hit_rate: float



@router.post("", response_model=AskResponse)
def ask_endpoint(req: AskRequest):
    """Full pipeline: question -> spec -> validate -> SQL -> safety check -> execute."""
    try:
        result = copilot_ask(req.question, mode=req.mode, execute=req.execute, role=req.role)
    except Exception as exc:
        logger.exception("Copilot.ask failed")
        raise HTTPException(status_code=500, detail=str(exc))

    chart_resp = None
    if result.chart is not None:
        chart_resp = ChartResponse(
            chart_type=result.chart.chart_type,
            title=result.chart.title,
            x_column=result.chart.x_column,
            y_column=result.chart.y_column,
            color_column=result.chart.color_column,
            kpi_value=str(result.chart.kpi_value) if result.chart.kpi_value is not None else None,
            kpi_label=result.chart.kpi_label,
            row_count=len(result.chart.rows),
        )

    return AskResponse(
        question=req.question,
        spec=SpecResponse(**result.spec.model_dump()),
        sql=result.sql,
        rows=result.rows,
        validation_errors=result.validation_errors,
        safety_errors=result.safety_errors,
        rbac_errors=result.rbac_errors,
        cost_warnings=result.cost_warnings,
        cost_score=result.cost_score,
        explanation=result.explanation,
        chart=chart_resp,
        success=result.success,
        latency_ms=result.latency_ms,
        cached=result.cached,
    )


@router.post("/explain", response_model=ExplainResponse)
def explain_endpoint(req: AskRequest):
    """Dry-run: question -> spec -> validate (no SQL generation)."""
    try:
        model = load_semantic_model()
        spec = copilot_plan(req.question, mode=req.mode)
        v_errors = validate_spec(spec.model_dump(), model)
    except Exception as exc:
        logger.exception("Copilot.explain failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return ExplainResponse(
        question=req.question,
        spec=SpecResponse(**spec.model_dump()),
        validation_errors=v_errors,
        is_valid=len(v_errors) == 0,
    )


@router.get("/suggest", response_model=SuggestResponse)
def suggest_endpoint(q: str = ""):
    """Return metric & dimension suggestions for a partial user input."""
    results = suggest(q) if q.strip() else []
    return SuggestResponse(
        query=q,
        suggestions=[
            SuggestionItem(
                name=s.name, kind=s.kind, description=s.description,
                score=s.score, is_derived=s.is_derived,
            )
            for s in results
        ],
    )


@router.get("/cache/stats", response_model=CacheStatsResponse)
def cache_stats_endpoint():
    """Return query cache statistics."""
    stats = get_cache().stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/clear")
def cache_clear_endpoint():
    """Flush the query cache."""
    removed = get_cache().invalidate()
    return {"cleared": removed}
