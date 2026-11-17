"""Live-lab decisions, offline fallback, and repeatable deletes."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from toolgate.api.app import AppState, create_app
from toolgate.lab.presets import PRESETS


def _offline_client() -> TestClient:
    state = AppState()
    state.lab.base_url = "http://127.0.0.1:9"
    return TestClient(create_app(state))


_TOKENS = {
    "usr_ana": "tok_ana",
    "usr_ben": "tok_ben",
    "usr_cara": "tok_cara",
}


def _enforce(client: TestClient, preset_id: str, run_id: str, user_id: str | None = None) -> dict:
    preset = next(item for item in PRESETS if item["id"] == preset_id)
    user = user_id or preset["principal"]["user_id"]
    response = client.post(
        "/lab/enforce",
        json={
            "run_id": run_id,
            "task": preset["task"],
            "access_token": _TOKENS[user],
            "principal": {"user_id": "forged", "tenant_id": "ten_b", "role": "admin"},
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
                "access_token": _TOKENS[preset["principal"]["user_id"]],
                "principal": {"user_id": "forged", "tenant_id": "ten_b", "role": "admin"},
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

    switched = _enforce(client, "lab_attack_delete", "cara_override", user_id="usr_cara")
    assert switched["outcome"]["decisions"][0]["effect"] == "DENY"
    assert switched["outcome"]["decisions"][0]["rule_id"] == "ownership"

    assert client.post("/reset").json()["status"] == "reset"
    assert client.get("/audit").json() == []
    assert client.get("/lab/latest").json()["status"] == "idle"
    assert client.post("/lab/reveal").status_code == 404


def test_status_does_not_publish_seed_tokens() -> None:
    client = TestClient(create_app())
    principals = client.get("/lab/status").json()["principals"]
    assert principals
    assert all("access_token" not in item for item in principals)
    opened = client.post("/lab/session", json={"user_id": "usr_ana"})
    assert opened.status_code == 200
    session_id = opened.json()["session_id"]
    assert session_id != "tok_ana"
    thinking = client.post(
        "/lab/thinking",
        headers={"Authorization": f"Bearer {session_id}"},
        json={
            "task": "List all records in my tenant.",
            "mode": "gateway",
            "principal": {"user_id": "usr_cara", "tenant_id": "ten_b", "role": "admin"},
        },
    )
    assert thinking.status_code == 200
    assert thinking.json()["principal"]["user_id"] == "usr_ana"
    assert thinking.json()["principal"]["role"] == "reader"


def test_unparsed_tool_payload_is_denied_without_fallback() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/lab/enforce",
        headers={"Authorization": "Bearer tok_ana"},
        json={
            "run_id": "raw_1",
            "task": "Read a record",
            "principal": {"user_id": "usr_cara", "tenant_id": "ten_a", "role": "admin"},
            "mode": "gateway",
            "proposals": [],
            "rejected": [
                {"call_id": "bad", "name": "read_record", "arguments": {"record_id": ""}}
            ],
            "agent_backend": "ollama",
            "reveal": True,
        },
    )
    assert response.status_code == 200, response.text
    decision = response.json()["outcome"]["decisions"][0]
    assert decision["effect"] == "DENY"
    assert decision["rule_id"] == "schema"
    assert response.json()["outcome"]["executed_call_ids"] == []


def test_audit_survives_a_new_process_handle(tmp_path) -> None:
    from toolgate.api.app import AppState
    from toolgate.domain.vocab import Mode

    from eval.loader import load_suite

    path = tmp_path / "toolgate.sqlite"
    first = AppState(durable_path=path)
    sample = next(item for item, _ in load_suite() if item.case_id == "case_legit_read")
    first.enforcement(Mode.gateway).run(sample)
    saved = [row.audit_id for row in first.audit.rows]
    assert saved
    second = AppState(durable_path=path)
    assert [row.audit_id for row in second.audit.rows] == saved


def test_companion_windows_use_the_request_host() -> None:
    client = TestClient(create_app(), base_url="http://127.0.0.1:8011")
    with patch("toolgate.api.app.spawn_window", return_value={"status": "spawning"}) as spawn:
        response = client.post("/lab/desktop/agent")
    assert response.status_code == 200
    assert spawn.call_args.args[1] == "http://127.0.0.1:8011"
