"""End-to-end checks across enforcement, API, and the labeled suite."""

from eval.loader import load_suite
from fastapi.testclient import TestClient

from toolgate.api import create_app
from toolgate.domain.vocab import Effect, Mode
from toolgate.enforcement import ModeEnforcement
from toolgate.store import SqliteStore, seed_store


def test_gateway_matches_oracles_for_full_suite() -> None:
    for case, oracle in load_suite():
        store = SqliteStore(":memory:")
        seed_store(store)
        outcome = ModeEnforcement(Mode.gateway, store).run(case)
        expected = {item.call_id: item.effect for item in oracle.expected}
        actual = {d.call_id: d.effect for d in outcome.decisions}
        assert actual == expected, case.case_id
        for call_id, effect in expected.items():
            if effect is Effect.ALLOW:
                assert call_id in outcome.executed_call_ids
            else:
                assert call_id not in outcome.executed_call_ids


def test_api_modes_reset_and_contrast() -> None:
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"
    assert "gateway" in client.get("/modes").json()["modes"]

    from pathlib import Path

    from toolgate.domain.models import Case

    case = Case.model_validate_json(
        (
            Path(__file__).resolve().parents[2]
            / "data"
            / "cases"
            / "attack"
            / "case_cross_tenant.json"
        ).read_text(encoding="utf-8")
    )
    payload = case.model_dump(mode="json")

    denied = client.post("/tasks", params={"mode": "gateway"}, json=payload)
    assert denied.status_code == 200
    assert denied.json()["decisions"][0]["effect"] == "DENY"

    allowed = client.post("/tasks", params={"mode": "direct"}, json=payload)
    assert allowed.status_code == 200
    assert allowed.json()["decisions"][0]["effect"] == "ALLOW"

    assert len(client.get("/audit").json()) == 2
    assert client.post("/reset").json() == {"status": "reset"}
    assert client.get("/audit").json() == []
