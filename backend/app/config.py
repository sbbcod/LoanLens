"""Application settings, read from environment variables (or a local .env file).

Nothing secret or environment-specific is written in the code. Locally the
values come from backend/.env; on Azure they come from Container Apps secrets.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Database. SQLite file locally; an Azure SQL connection string when deployed.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'loanlens.db'}"

    # Where uploaded PDFs are kept.
    storage_dir: Path = BACKEND_DIR / "storage"

    # LLM. "mock" answers from the sample ground truth so the whole pipeline
    # runs without an API key; "anthropic" calls the real model.
    llm_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5-5"
    # How hard the model thinks: low | medium | high. Reading a few pages of a
    # loan application is routine work, so medium is the starting point.
    llm_effort: Literal["low", "medium", "high"] = "medium"

    # LLM answers are cached by document hash, so re-running the same PDF
    # (seeding, evaluation, development) doesn't pay for the same call twice.
    llm_cache_dir: Path = BACKEND_DIR / ".llm_cache"

    # Date that valuation age is measured against. Fixed so the demo and the
    # evaluation give the same results whenever they are run.
    assessment_date: date = date(2026, 11, 1)

    # Every endpoint that changes data needs the X-API-Key header to match one of these.
    # api_key is for systems (Power Automate); demo_passcode is what a person types
    # into the web page. Separate, so one can be changed without breaking the other.
    api_key: str = Field(default="change-me", min_length=8)
    demo_passcode: str = Field(default="loanlens-demo", min_length=6)

    # Power Automate approval flow ("When an HTTP request is received" trigger URL).
    # Empty = approvals are simulated locally and decided through the callback endpoint.
    approval_flow_url: str | None = None

    # Where the front end lives, for "Open in LoanLens" links in Teams.
    frontend_url: str = "http://localhost:5173"

    # Largest PDF accepted, in megabytes.
    max_upload_mb: int = 10

    # Front-end origins allowed to call the API from a browser.
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
