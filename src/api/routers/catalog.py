"""
GET /metrics, GET /dimensions, GET /catalog -- metadata endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.governance.semantic_loader import load_semantic_model

router = APIRouter()



class MetricItem(BaseModel):
    name: str
    description: str
    is_derived: bool


class DimensionItem(BaseModel):
    name: str
    column: str
    grains: list[str]


class CatalogResponse(BaseModel):
    metrics: list[MetricItem]
    dimensions: list[DimensionItem]
    allowed_tables: list[str]
    max_rows: int



@router.get("/metrics")
def list_metrics() -> dict:
    """Return queryable (non-derived) metric names."""
    model = load_semantic_model()
    return {"metrics": model.get_metric_names()}


@router.get("/metrics/detail", response_model=list[MetricItem])
def list_metrics_detail() -> list[MetricItem]:
    """Return enriched metadata for queryable (non-derived) metrics."""
    model = load_semantic_model()
    return [
        MetricItem(name=m.name, description=m.description, is_derived=m.is_derived)
        for m in model.metrics.values()
        if not m.is_derived
    ]


@router.get("/dimensions")
def list_dimensions() -> dict:
    """Return all dimension names (lightweight)."""
    model = load_semantic_model()
    return {"dimensions": model.get_dimension_names()}


@router.get("/dimensions/detail", response_model=list[DimensionItem])
def list_dimensions_detail() -> list[DimensionItem]:
    """Return enriched dimension metadata."""
    model = load_semantic_model()
    return [
        DimensionItem(name=d.name, column=d.column, grains=d.grains)
        for d in model.dimensions.values()
    ]


@router.get("/catalog", response_model=CatalogResponse)
def full_catalog() -> CatalogResponse:
    """Return the complete semantic-layer catalog for the UI sidebar."""
    model = load_semantic_model()
    return CatalogResponse(
        metrics=[
            MetricItem(name=m.name, description=m.description, is_derived=m.is_derived)
            for m in model.metrics.values()
            if not m.is_derived
        ],
        dimensions=[
            DimensionItem(name=d.name, column=d.column, grains=d.grains)
            for d in model.dimensions.values()
        ],
        allowed_tables=sorted(model.allowed_tables),
        max_rows=model.security.max_rows,
    )
