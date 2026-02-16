"""
Centralised application settings loaded from environment / .env file.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH)


class Settings(BaseSettings):
    # ── Postgres ─────────────────────────────────────────
    postgres_user: str = "copilot"
    postgres_password: str = "copilot_pw"
    postgres_db: str = "analytics"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ── LLM ──────────────────────────────────────────────
    llm_provider: str = "mock"  # mock | openai | anthropic
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── App ──────────────────────────────────────────────
    api_port: int = 8000
    streamlit_port: int = 8501
    log_level: str = "INFO"
    sql_row_limit: int = 200

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
