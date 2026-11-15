"""In-memory stand-ins. Later tracks import these until their own packages exist."""

from datetime import datetime, timezone

from toolgate.domain.models import (
    Approval,
    AuditRecord,
    Case,
    Decision,
    Outcome,
    Principal,
    Record,
    ToolCall,
    ToolResult,
)
from toolgate.domain.vocab import RECORD_FIELDS, Effect, Mode, Role, RuleId, ToolStatus


class FakeStore:
    def __init__(self) -> None:
        self.records: dict[str, Record] = {}
        self.users: dict[str, Principal] = {}
        self.approvals: dict[str, Approval] = {}
        self.audits: list[AuditRecord] = []

    def seed(
        self,
        records: list[Record] | None = None,
        users: list[Principal] | None = None,
        approvals: list[Approval] | None = None,
    ) -> None:
        for record in records or []:
            self.records[record.record_id] = record
        for user in users or []:
            self.users[user.user_id] = user
        for approval in approvals or []:
            self.approvals[approval.token] = approval

    def get_record(self, record_id: str) -> Record | None:
        return self.records.get(record_id)

    def list_records(self, tenant_id: str) -> list[Record]:
        return [record for record in self.records.values() if record.tenant_id == tenant_id]

    def create_record(self, record: Record) -> Record:
        if record.record_id in self.records:
            raise ValueError(f"record already exists: {record.record_id}")
        self.records[record.record_id] = record
        return record

    def update_record(self, record_id: str, fields: dict[str, str]) -> Record | None:
        current = self.records.get(record_id)
        if current is None:
            return None
        unknown = set(fields) - RECORD_FIELDS
        if unknown:
            raise ValueError(f"fields has unknown keys: {', '.join(sorted(unknown))}")
        updated = current.model_copy(update=fields)
        self.records[record_id] = updated
        return updated

    def delete_record(self, record_id: str) -> bool:
        if record_id not in self.records:
            return False
        del self.records[record_id]
        return True

    def search_records(self, tenant_id: str, field: str, value: str) -> list[Record]:
        return [
            record
            for record in self.list_records(tenant_id)
            if getattr(record, field) == value
        ]

    def export_records(self, tenant_id: str) -> list[Record]:
        return self.list_records(tenant_id)

    def get_user(self, user_id: str) -> Principal | None:
        return self.users.get(user_id)

    def set_role(self, user_id: str, role: Role) -> Principal | None:
        current = self.users.get(user_id)
        if current is None:
            return None
        updated = current.model_copy(update={"role": role})
        self.users[user_id] = updated
        return updated

    def get_approval(self, token: str) -> Approval | None:
        return self.approvals.get(token)

    def save_audit(self, record: AuditRecord) -> AuditRecord:
        self.audits.append(record)
        return record


def seeded_store() -> FakeStore:
    store = FakeStore()
    store.seed(
        records=[
            Record(
                record_id="rec_a1",
                tenant_id="ten_a",
                owner_id="usr_ana",
                title="Note",
                body="Ana's note",
            ),
            Record(
                record_id="rec_b1",
                tenant_id="ten_b",
                owner_id="usr_ben",
                title="Other",
                body="Ben's note",
            ),
        ],
        users=[
            Principal(user_id="usr_ana", tenant_id="ten_a", role=Role.reader),
            Principal(user_id="usr_ben", tenant_id="ten_b", role=Role.editor),
        ],
    )
    return store


class FakePolicy:
    def __init__(self, decisions: dict[str, Decision] | None = None) -> None:
        self.decisions = dict(decisions or {})

    def decide(
        self,
        call: ToolCall,
        principal: Principal,
        record: Record | None,
        approvals: list[Approval],
    ) -> Decision:
        del principal, record, approvals
        scripted = self.decisions.get(call.call_id)
        if scripted is not None:
            return scripted
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.default,
            reason="no scripted decision",
        )


class FakeAgent:
    def propose(self, case: Case) -> list[ToolCall]:
        return list(case.proposals)


class FakeToolRuntime:
    def execute(self, call: ToolCall, store: FakeStore) -> ToolResult:
        del store
        return ToolResult(
            call_id=call.call_id,
            status=ToolStatus.ok,
            payload={"name": call.name.value, "arguments": call.arguments},
        )


class FakeAudit:
    def __init__(self) -> None:
        self.rows: list[AuditRecord] = []

    def record(self, decision: Decision, principal: Principal, call: ToolCall) -> AuditRecord:
        row = AuditRecord(
            audit_id=f"aud_{len(self.rows) + 1}",
            call_id=decision.call_id,
            effect=decision.effect,
            rule_id=decision.rule_id,
            reason=decision.reason,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            tool_name=call.name,
            created_at=datetime.now(timezone.utc),
        )
        self.rows.append(row)
        return row


class FakeEnforcement:
    """Reference behavior for the three modes. Gateway uses the scripted policy."""

    def __init__(self, policy: FakePolicy, mode: Mode = Mode.gateway) -> None:
        self.policy = policy
        self.mode = mode

    def run(self, case: Case) -> Outcome:
        decisions: list[Decision] = []
        results: list[ToolResult] = []
        executed: list[str] = []
        for call in case.proposals:
            decision = self._decide(case, call)
            decisions.append(decision)
            if decision.effect is Effect.ALLOW:
                executed.append(call.call_id)
                results.append(
                    ToolResult(call_id=call.call_id, status=ToolStatus.ok, payload={})
                )
        return Outcome(
            case_id=case.case_id,
            mode=self.mode,
            decisions=decisions,
            results=results,
            executed_call_ids=executed,
            decision_latency_ms=0,
            tool_latency_ms=0,
        )

    def _decide(self, case: Case, call: ToolCall) -> Decision:
        if self.mode is Mode.direct:
            return Decision(
                call_id=call.call_id,
                effect=Effect.ALLOW,
                rule_id=RuleId.direct,
                reason="direct mode executes the proposal",
            )
        if self.mode is Mode.prompt_only:
            effect = Effect.ALLOW if case.prompt_only_would_execute else Effect.DENY
            return Decision(
                call_id=call.call_id,
                effect=effect,
                rule_id=RuleId.prompt_only,
                reason="prompt-only baseline",
            )
        return self.policy.decide(call, case.principal, None, [])
