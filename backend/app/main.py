"""LoanLens API entry point.

Run locally from the backend folder:

    .venv/bin/uvicorn app.main:app --reload

then open http://localhost:8000/docs
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, init_db
from app.routers import admin, applications, approvals, ingest, metrics

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Runs once when the server starts."""
    init_db()
    yield


app = FastAPI(
    title="LoanLens API",
    version=VERSION,
    description="Commercial loan intake: AI extraction with evidence, deterministic "
                "policy checks, human review and approval.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(applications.router)
app.include_router(approvals.router)
app.include_router(metrics.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Used by Azure Container Apps to check the service is alive.

    Also checks the database answers, so a broken connection shows up here
    rather than on the first real request.
    """
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "version": VERSION,
        "database": "ok",
        "llm_provider": get_settings().llm_provider,
    }
