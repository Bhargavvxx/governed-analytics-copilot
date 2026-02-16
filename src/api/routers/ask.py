"""POST /ask -- main copilot endpoint."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from src.copilot.service import ask as copilot_ask
from src.copilot.planner import plan as copilot_plan
from src.governance.validator import validate_spec
from src.governance.semantic_loader import load_semantic_model
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()



class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Natural-language business question")
    mode: str = Field("mock", description="mock | openai | anthropic")
    execute: bool = Field(True, description="If true, run SQL against Postgres and return rows")


class SpecResponse(BaseModel):
    metric: str
    dimensions: list[str]
    filters: dict
    time_grain: str | None
    time_range: str | None
    limit: int


class AskResponse(BaseModel):
    question: str
    spec: SpecResponse
    sql: str
    rows: list[dict]
    validation_errors: list[str]
    safety_errors: list[str]
    success: bool
    latency_ms: int


class ExplainResponse(BaseModel):
    question: str
    spec: SpecResponse
    validation_errors: list[str]
    is_valid: bool



@router.post("", response_model=AskResponse)
def ask_endpoint(req: AskRequest):
    """Full pipeline: question -> spec -> validate -> SQL -> safety check -> execute."""
    try:
        result = copilot_ask(req.question, mode=req.mode, execute=req.execute)
    except Exception as exc:
        logger.exception("Copilot.ask failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return AskResponse(
        question=req.question,
        spec=SpecResponse(**result.spec.model_dump()),
        sql=result.sql,
        rows=result.rows,
        validation_errors=result.validation_errors,
        safety_errors=result.safety_errors,
        success=result.success,
        latency_ms=result.latency_ms,
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
