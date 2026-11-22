"""The API as a reviewer and Power Automate would use it."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
KEY = {"X-API-Key": "test-api-key", "X-User-Name": "Sarah"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def upload(client, sample: str, headers=KEY):
    with open(SAMPLES / f"{sample}.pdf", "rb") as f:
        return client.post("/api/ingest", headers=headers, data={"source": "email"},
                           files={"file": (f"{sample}.pdf", f, "application/pdf")})


def test_writes_need_a_key(client):
    assert upload(client, "S01", headers={}).status_code == 401
    assert upload(client, "S01", headers={"X-API-Key": "wrong-key"}).status_code == 401


def test_only_pdfs_are_accepted(client):
    r = client.post("/api/ingest", headers=KEY,
                    files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_ingest_processes_and_lists(client):
    r = upload(client, "S01")
    assert r.status_code == 202
    app_id = r.json()["id"]
    # TestClient runs background tasks before returning, so it's processed already.
    detail = client.get(f"/api/applications/{app_id}").json()
    assert detail["status"] == "extracted"
    assert detail["borrower_name"] == "Kestrel Point Holdings Pty Ltd"
    assert len(detail["fields"]) == 16
    assert client.get(f"/api/applications/{app_id}/pdf").headers["content-type"] == "application/pdf"
    listed = client.get("/api/applications", params={"q": "kestrel"}).json()
    assert [a["id"] for a in listed] == [app_id]


def test_correcting_a_field_reruns_the_rules_and_keeps_the_ai_value(client):
    app_id = upload(client, "S08").json()["id"]  # land, LVR 52% > 50%
    before = client.get(f"/api/applications/{app_id}").json()
    assert "LVR_OVER_LIMIT" in {r["code"] for r in before["risks"]}

    r = client.patch(f"/api/applications/{app_id}/fields", headers=KEY,
                     json={"changes": {"loan_amount": 1_450_000}})
    after = r.json()
    assert "LVR_OVER_LIMIT" not in {r["code"] for r in after["risks"]}
    loan = next(f for f in after["fields"] if f["name"] == "loan_amount")
    assert loan["value"] == 1_450_000 and loan["ai_value"] == 1_560_000
    assert loan["edited_by"] == "user:Sarah"
    assert after["audit"][-1]["action"] == "field_edited"


def test_bad_values_are_rejected(client):
    app_id = upload(client, "S01").json()["id"]
    r = client.patch(f"/api/applications/{app_id}/fields", headers=KEY,
                     json={"changes": {"loan_amount": "lots"}})
    assert r.status_code == 422


def test_approval_flow_end_to_end(client):
    app_id = upload(client, "S02").json()["id"]  # LVR 70%: critical
    blocked = client.post(f"/api/applications/{app_id}/submit-for-approval", headers=KEY, json={})
    assert blocked.status_code == 409 and "LVR_OVER_LIMIT" in blocked.json()["detail"]

    detail = client.get(f"/api/applications/{app_id}").json()
    critical = next(r for r in detail["risks"] if r["severity"] == "critical")
    client.post(f"/api/applications/{app_id}/acknowledge-risk", headers=KEY,
                json={"risk_id": critical["id"]})

    submitted = client.post(f"/api/applications/{app_id}/submit-for-approval", headers=KEY,
                            json={"comment": "Strong tenant; LVR exception requested."})
    assert submitted.json()["status"] == "pending_approval"

    # Locked while with the manager.
    assert client.patch(f"/api/applications/{app_id}/fields", headers=KEY,
                        json={"changes": {"loan_term_months": 12}}).status_code == 409

    decision = {"application_id": app_id, "decision": "approved", "approver": "Tom",
                "flow_run_id": "run-123"}
    assert client.post("/api/approvals/callback", headers=KEY, json=decision).status_code == 200
    final = client.get(f"/api/applications/{app_id}").json()
    assert final["status"] == "approved"
    assert final["approvals"][0]["approver"] == "Tom"
    # A retried callback must not decide twice.
    assert client.post("/api/approvals/callback", headers=KEY, json=decision).status_code == 409


def test_submitting_calls_the_approval_flow_with_a_ready_card(client, monkeypatch):
    from app.config import get_settings
    from app.services import power_automate

    sent: dict = {}

    class Ok:
        def raise_for_status(self) -> None:
            pass

    def fake_post(url: str, json: dict, timeout: float) -> Ok:
        sent.update(url=url, body=json)
        return Ok()

    monkeypatch.setattr(get_settings(), "approval_flow_url", "https://flow.example/trigger")
    monkeypatch.setattr(power_automate.httpx, "post", fake_post)

    app_id = upload(client, "S08").json()["id"]  # land, LVR 52% > 50%: critical
    detail = client.get(f"/api/applications/{app_id}").json()
    critical = next(r for r in detail["risks"] if r["severity"] == "critical")
    client.post(f"/api/applications/{app_id}/acknowledge-risk", headers=KEY,
                json={"risk_id": critical["id"]})
    r = client.post(f"/api/applications/{app_id}/submit-for-approval", headers=KEY,
                    json={"comment": "Valuation is recent."})
    assert r.status_code == 200

    body = sent["body"]
    assert sent["url"] == "https://flow.example/trigger"
    assert body["application_id"] == app_id
    assert body["review_url"].endswith(f"/applications/{app_id}")
    details = body["details"]
    assert "**Loan:** $1,560,000 · Purchase · Land" in details
    assert "**LVR:** 52.0%" in details
    assert "**Submitted by:** Sarah — Valuation is recent." in details
    assert "- Critical:" in details and "(Policy §4.2)" in details and "acknowledged by Sarah" in details


def test_metrics(client):
    m = client.get("/api/metrics").json()
    assert m["total"] >= 4
    assert 0 < m["human_edit_rate"] < 1
    assert len(m["daily"]) == 14
