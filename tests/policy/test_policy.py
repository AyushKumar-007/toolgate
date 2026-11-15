from toolgate.domain.models import Approval, Principal, Record, ToolCall
from toolgate.domain.vocab import Effect, Role, RuleId, ToolName
from toolgate.policy import PolicyEngine


def _engine() -> PolicyEngine:
    return PolicyEngine()


def _ana() -> Principal:
    return Principal(user_id="usr_ana", tenant_id="ten_a", role=Role.reader)


def _rec_a1() -> Record:
    return Record(
        record_id="rec_a1",
        tenant_id="ten_a",
        owner_id="usr_ana",
        title="Ana note",
        body="Owned by Ana",
    )


def _rec_b1() -> Record:
    return Record(
        record_id="rec_b1",
        tenant_id="ten_b",
        owner_id="usr_ben",
        title="Ben note",
        body="Owned by Ben",
    )


def test_allow_legit_read() -> None:
    call = ToolCall(call_id="c1", name=ToolName.read_record, arguments={"record_id": "rec_a1"})
    decision = _engine().decide(call, _ana(), _rec_a1(), [])
    assert decision.effect is Effect.ALLOW
    assert decision.rule_id is RuleId.default


def test_deny_cross_tenant() -> None:
    call = ToolCall(call_id="c1", name=ToolName.read_record, arguments={"record_id": "rec_b1"})
    decision = _engine().decide(call, _ana(), _rec_b1(), [])
    assert decision.effect is Effect.DENY
    assert decision.rule_id is RuleId.tenant


def test_deny_prohibited_tool() -> None:
    call = ToolCall(
        call_id="c1",
        name=ToolName.delete_record,
        arguments={"record_id": "rec_a1", "approval_token": "apr_x"},
    )
    decision = _engine().decide(call, _ana(), _rec_a1(), [])
    assert decision.effect is Effect.DENY
    assert decision.rule_id is RuleId.actions


def test_deny_ownership_mismatch() -> None:
    ben = Principal(user_id="usr_ben", tenant_id="ten_b", role=Role.editor)
    call = ToolCall(
        call_id="c1",
        name=ToolName.create_record,
        arguments={
            "tenant_id": "ten_b",
            "owner_id": "usr_ana",
            "title": "x",
            "body": "y",
        },
    )
    decision = _engine().decide(call, ben, None, [])
    assert decision.effect is Effect.DENY
    assert decision.rule_id is RuleId.ownership


def test_deny_missing_context() -> None:
    call = ToolCall(call_id="c1", name=ToolName.list_records, arguments={"tenant_id": "ten_a"})
    principal = Principal.model_construct(user_id="", tenant_id="ten_a", role=Role.reader)
    decision = _engine().decide(call, principal, None, [])
    assert decision.effect is Effect.DENY
    assert decision.rule_id is RuleId.context


def test_deny_approval_missing() -> None:
    cara = Principal(user_id="usr_cara", tenant_id="ten_a", role=Role.admin)
    call = ToolCall(
        call_id="c1",
        name=ToolName.delete_record,
        arguments={"record_id": "rec_a1", "approval_token": "apr_wrong"},
    )
    decision = _engine().decide(call, cara, _rec_a1(), [])
    assert decision.effect is Effect.DENY
    assert decision.rule_id is RuleId.approval


def test_allow_with_matching_approval() -> None:
    cara = Principal(user_id="usr_cara", tenant_id="ten_a", role=Role.admin)
    call = ToolCall(
        call_id="c1",
        name=ToolName.delete_record,
        arguments={"record_id": "rec_a1", "approval_token": "apr_delete_a1"},
    )
    approvals = [
        Approval(
            token="apr_delete_a1",
            tool_name=ToolName.delete_record,
            resource_id="rec_a1",
            user_id="usr_cara",
        )
    ]
    decision = _engine().decide(call, cara, _rec_a1(), approvals)
    assert decision.effect is Effect.ALLOW


def test_deny_malformed_extra_arg() -> None:
    call = ToolCall(
        call_id="c1",
        name=ToolName.read_record,
        arguments={"record_id": "rec_a1", "extra_flag": "1"},
    )
    decision = _engine().decide(call, _ana(), _rec_a1(), [])
    assert decision.effect is Effect.DENY
    assert decision.rule_id is RuleId.schema
