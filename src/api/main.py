"""
FastAPI application entry-point.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import ask, catalog

app = FastAPI(
    title="Governed Analytics Copilot",
    version="0.1.0",
    description="NL-to-SQL copilot governed by a semantic layer",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask.router, prefix="/ask", tags=["Copilot"])
app.include_router(catalog.router, tags=["Catalog"])


@app.get("/health")
def health():
    return {"status": "ok"}
