from pathlib import Path

from fastapi.testclient import TestClient

from toolgate.api import create_app
from toolgate.domain.models import Case
from toolgate.domain.vocab import Effect, Mode, ToolName

CASES = Path(__file__).resolve().parents[2] / "data" / "cases"


def test_health_and_task_and_audit() -> None:
    client = TestClient(create_app())
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert "version" in health

    case = Case.model_validate_json(
        (CASES / "legitimate" / "case_legit_read.json").read_text(encoding="utf-8")
    )
    response = client.post("/tasks", params={"mode": Mode.gateway.value}, json=case.model_dump(mode="json"))
    assert response.status_code == 200
    body = response.json()
    assert body["decisions"][0]["effect"] == Effect.ALLOW.value
    assert body["executed_call_ids"] == ["call_legit_read"]

    audits = client.get("/audit").json()
    assert len(audits) == 1
    assert audits[0]["call_id"] == "call_legit_read"


def test_create_approval() -> None:
    client = TestClient(create_app())
    payload = {
        "token": "apr_new",
        "tool_name": ToolName.export_records.value,
        "resource_id": "ten_a",
        "user_id": "usr_cara",
        "expires_at": None,
    }
    response = client.post("/approvals", json=payload)
    assert response.status_code == 200
    assert response.json()["token"] == "apr_new"


def test_gateway_denies_attack_via_api() -> None:
    client = TestClient(create_app())
    case = Case.model_validate_json(
        (CASES / "attack" / "case_cross_tenant.json").read_text(encoding="utf-8")
    )
    response = client.post("/tasks", params={"mode": "gateway"}, json=case.model_dump(mode="json"))
    assert response.status_code == 200
    assert response.json()["decisions"][0]["effect"] == "DENY"
