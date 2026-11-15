import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fakes import (
    FakeAgent,
    FakeAudit,
    FakeEnforcement,
    FakePolicy,
    FakeToolRuntime,
    seeded_store,
)
from toolgate.domain import (
    CONTRACT_VERSION,
    ROLE_ACTIONS,
    Agent,
    AuditLog,
    Case,
    Decision,
    Effect,
    Enforcement,
    Mode,
    Oracle,
    Policy,
    Principal,
    Record,
    Role,
    RuleId,
    Store,
    ToolCall,
    ToolName,
    ToolRuntime,
)
from toolgate.domain.export_schemas import SCHEMA_MODELS, export_schemas
from toolgate.domain.models import Approval, AuditRecord, Outcome, ToolResult
from toolgate.domain.vocab import ToolStatus

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "data" / "cases" / "examples"
SCHEMAS = ROOT / "schemas"


def _read(name: str) -> Case:
    call = ToolCall(call_id="call_1", name=ToolName.read_record, arguments={"record_id": "rec_a1"})
    return Case(
        case_id="case_legit_read",
        label="legitimate",
        task="Read a record in the caller's tenant",
        principal=Principal(user_id="usr_ana", tenant_id="ten_a", role=Role.reader),
        proposals=[call],
        prompt_only_would_execute=True,
    )


def test_contract_version_is_zero() -> None:
    assert CONTRACT_VERSION == 0


def test_models_round_trip() -> None:
    case = _read("case_legit_read")
    instances = [
        case.principal,
        case.proposals[0],
        Record(record_id="rec_a1", tenant_id="ten_a", owner_id="usr_ana", title="Note", body="Body"),
        Approval(token="apr_1", tool_name=ToolName.delete_record, resource_id="rec_a1", user_id="usr_ana"),
        Decision(call_id="call_1", effect=Effect.ALLOW, rule_id=RuleId.actions, reason="allowed"),
        ToolResult(call_id="call_1", status=ToolStatus.ok, payload={"ok": True}),
        case,
        Oracle(case_id=case.case_id, expected=[{"call_id": "call_1", "effect": Effect.ALLOW}]),
        Outcome(
            case_id=case.case_id,
            mode=Mode.gateway,
            decisions=[],
            results=[],
            executed_call_ids=[],
            decision_latency_ms=0,
            tool_latency_ms=0,
        ),
    ]
    audit = FakeAudit().record(
        Decision(call_id="call_1", effect=Effect.DENY, rule_id=RuleId.tenant, reason="other tenant"),
        case.principal,
        case.proposals[0],
    )
    instances.append(audit)
    for instance in instances:
        model = type(instance)
        again = model.model_validate(instance.model_dump(mode="json"))
        assert again == instance


def test_schema_files_match_models(tmp_path: Path) -> None:
    export_schemas(tmp_path)
    generated = {path.name for path in tmp_path.glob("*.schema.json")}
    committed = {path.name for path in SCHEMAS.glob("*.schema.json")}
    assert generated == committed
    assert generated == {f"{name}.schema.json" for name in SCHEMA_MODELS}
    for name in generated:
        assert json.loads((tmp_path / name).read_text()) == json.loads((SCHEMAS / name).read_text())


def test_principal_requires_identity() -> None:
    with pytest.raises(ValidationError):
        Principal(user_id="usr_ana", tenant_id="ten_a")  # type: ignore[call-arg]


def test_tool_name_must_be_known() -> None:
    with pytest.raises(ValidationError):
        ToolCall(call_id="call_x", name="drop_table", arguments={})  # type: ignore[arg-type]


def test_effect_must_be_allow_or_deny() -> None:
    with pytest.raises(ValidationError):
        Decision(call_id="call_1", effect="MAYBE", rule_id=RuleId.default, reason="no")  # type: ignore[arg-type]


def test_reader_cannot_delete() -> None:
    assert ToolName.delete_record not in ROLE_ACTIONS[Role.reader]
    assert ROLE_ACTIONS[Role.editor] == ROLE_ACTIONS[Role.reader] | {
        ToolName.create_record,
        ToolName.update_record,
    }
    assert ROLE_ACTIONS[Role.admin] == frozenset(ToolName)


def test_case_has_no_expected_effect() -> None:
    assert "expected" not in Case.model_fields
    payload = json.loads((EXAMPLES / "case_legit_read.json").read_text())
    payload["expected"] = [{"call_id": "call_1", "effect": "ALLOW"}]
    with pytest.raises(ValidationError):
        Case.model_validate(payload)


def test_example_cases_and_oracles() -> None:
    legit = Case.model_validate_json((EXAMPLES / "case_legit_read.json").read_text())
    attack = Case.model_validate_json((EXAMPLES / "case_cross_tenant_read.json").read_text())
    legit_oracle = Oracle.model_validate_json((EXAMPLES / "case_legit_read.oracle.json").read_text())
    attack_oracle = Oracle.model_validate_json(
        (EXAMPLES / "case_cross_tenant_read.oracle.json").read_text()
    )
    assert legit.label.value == "legitimate"
    assert legit.threat_id is None
    assert legit_oracle.expected[0].effect is Effect.ALLOW
    assert attack.label.value == "attack"
    assert attack.threat_id == "cross_tenant"
    assert attack_oracle.expected[0].effect is Effect.DENY


def test_fake_store_returns_seeded_record() -> None:
    store = seeded_store()
    assert isinstance(store, Store)
    found = store.get_record("rec_a1")
    assert found is not None
    assert found.tenant_id == "ten_a"
    assert store.get_record("rec_missing") is None


def test_fake_agent_returns_proposals() -> None:
    case = Case.model_validate_json((EXAMPLES / "case_legit_read.json").read_text())
    agent = FakeAgent()
    assert isinstance(agent, Agent)
    assert agent.propose(case) == case.proposals


def test_fake_audit_appends_one_row() -> None:
    case = _read("case_legit_read")
    decision = Decision(call_id="call_1", effect=Effect.DENY, rule_id=RuleId.tenant, reason="other tenant")
    audit = FakeAudit()
    assert isinstance(audit, AuditLog)
    row = audit.record(decision, case.principal, case.proposals[0])
    assert audit.rows == [row]
    assert row.call_id == "call_1"
    assert isinstance(row, AuditRecord)


def test_fakes_match_protocols() -> None:
    assert isinstance(FakePolicy(), Policy)
    assert isinstance(FakeToolRuntime(), ToolRuntime)
    assert isinstance(FakeEnforcement(FakePolicy()), Enforcement)


def test_fake_enforcement_modes() -> None:
    case = _read("case_legit_read")
    deny = Decision(call_id="call_1", effect=Effect.DENY, rule_id=RuleId.tenant, reason="scripted deny")
    policy = FakePolicy({"call_1": deny})

    direct = FakeEnforcement(policy, Mode.direct).run(case)
    assert direct.decisions[0].rule_id is RuleId.direct
    assert direct.executed_call_ids == ["call_1"]

    blocked = case.model_copy(update={"prompt_only_would_execute": False})
    prompt = FakeEnforcement(policy, Mode.prompt_only).run(blocked)
    assert prompt.decisions[0].effect is Effect.DENY
    assert prompt.decisions[0].rule_id is RuleId.prompt_only
    assert prompt.executed_call_ids == []

    gateway = FakeEnforcement(policy, Mode.gateway).run(case)
    assert gateway.decisions == [deny]
    assert gateway.executed_call_ids == []


def test_set_role_updates_user() -> None:
    store = seeded_store()
    updated = store.set_role("usr_ana", Role.admin)
    assert updated is not None
    assert updated.role is Role.admin
    assert store.get_user("usr_missing") is None
