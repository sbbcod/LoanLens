from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import engine
from app.main import app


def test_health_reports_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["llm_provider"] == "mock"


def test_startup_creates_all_tables() -> None:
    with TestClient(app):
        tables = set(inspect(engine).get_table_names())
    assert tables == {
        "applications", "extracted_fields", "risk_flags",
        "approvals", "audit_log", "llm_calls",
    }
