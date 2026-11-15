from toolgate.audit import AuditService
from toolgate.domain.models import Decision, Principal, ToolCall
from toolgate.domain.protocols import AuditLog
from toolgate.domain.vocab import Effect, Role, RuleId, ToolName
from toolgate.store import SqliteStore, seed_store


def test_audit_appends_and_persists() -> None:
    store = SqliteStore(":memory:")
    seed_store(store)
    audit = AuditService(store)
    assert isinstance(audit, AuditLog)
    decision = Decision(
        call_id="call_1",
        effect=Effect.DENY,
        rule_id=RuleId.tenant,
        reason="cross tenant",
    )
    principal = Principal(user_id="usr_ana", tenant_id="ten_a", role=Role.reader)
    call = ToolCall(call_id="call_1", name=ToolName.read_record, arguments={"record_id": "rec_b1"})
    row = audit.record(decision, principal, call)
    assert audit.rows == [row]
    assert store.list_audits() == [row]
