"""Live-lab decisions, offline fallback, and repeatable deletes."""

from fastapi.testclient import TestClient

from toolgate.api.app import AppState, create_app
from toolgate.lab.presets import PRESETS


def _offline_client() -> TestClient:
    state = AppState()
    state.lab.base_url = "http://127.0.0.1:9"
    return TestClient(create_app(state))


def _enforce(client: TestClient, preset_id: str, run_id: str, principal: dict | None = None) -> dict:
    preset = next(item for item in PRESETS if item["id"] == preset_id)
    response = client.post(
        "/lab/enforce",
        json={
            "run_id": run_id,
            "task": preset["task"],
            "principal": principal or preset["principal"],
            "mode": "gateway",
            "proposals": [preset["fallback_proposal"]],
            "agent_backend": "fallback",
            "model": "scripted",
            "preset_id": preset_id,
            "reveal": False,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_every_preset_falls_back_when_ollama_is_down() -> None:
    client = _offline_client()
    for preset in PRESETS:
        assert "fallback_proposal" in preset
        response = client.post(
            "/lab/propose",
            json={
                "task": preset["task"],
                "principal": preset["principal"],
                "preset_id": preset["id"],
                "allow_fallback": True,
                "model": "missing",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["agent_backend"] == "fallback"
        assert body["proposals"][0]["name"] == preset["fallback_proposal"]["name"]


def test_gateway_decisions_and_repeatable_admin_delete() -> None:
    client = TestClient(create_app())
    expected = {
        "lab_safe_list": ("ALLOW", "default", True),
        "lab_safe_read": ("ALLOW", "default", True),
        "lab_safe_search": ("ALLOW", "default", True),
        "lab_attack_cross_tenant": ("DENY", "tenant", False),
        "lab_attack_delete": ("DENY", "actions", False),
        "lab_safe_delete": ("ALLOW", "default", True),
        "lab_attack_export": ("DENY", "approval", False),
        "lab_attack_escalate": ("DENY", "actions", False),
        "lab_safe_approved_export": ("ALLOW", "default", True),
    }

    for preset_id, (effect, rule_id, executes) in expected.items():
        assert client.post("/reset").status_code == 200
        lab = _enforce(client, preset_id, preset_id)
        decision = lab["outcome"]["decisions"][0]
        assert decision["effect"] == effect
        assert decision["rule_id"] == rule_id
        assert bool(lab["outcome"]["executed_call_ids"]) is executes
        assert client.get("/lab/latest").json()["status"] == "evaluating"
        revealed = client.post("/lab/reveal")
        assert revealed.status_code == 200
        assert revealed.json()["status"] == "done"
        if effect == "DENY":
            assert lab["outcome"]["results"] == []

    assert client.post("/reset").status_code == 200
    first = _enforce(client, "lab_safe_delete", "admin_once")
    assert first["outcome"]["decisions"][0]["effect"] == "ALLOW"
    second = _enforce(client, "lab_safe_delete", "admin_again")
    denied = second["outcome"]["decisions"][0]
    assert denied["effect"] == "DENY"
    assert "not found" in denied["reason"]
    assert "already deleted" in (second["misuse_note"] or "")

    assert client.post("/reset").status_code == 200
    third = _enforce(client, "lab_safe_delete", "admin_reseeded")
    assert third["outcome"]["decisions"][0]["effect"] == "ALLOW"

    switched = _enforce(
        client,
        "lab_attack_delete",
        "cara_override",
        principal={"user_id": "usr_cara", "tenant_id": "ten_a", "role": "admin"},
    )
    assert switched["outcome"]["decisions"][0]["effect"] == "ALLOW"
    assert switched["misuse_note"] is None

    assert client.post("/reset").json()["status"] == "reset"
    assert client.get("/audit").json() == []
    assert client.get("/lab/latest").json()["status"] == "idle"
    assert client.post("/lab/reveal").status_code == 404
