"""Structural interfaces. Later tracks implement these and test against the fakes."""

from typing import Protocol, runtime_checkable

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
from toolgate.domain.vocab import Role


@runtime_checkable
class Store(Protocol):
    def get_record(self, record_id: str) -> Record | None: ...

    def list_records(self, tenant_id: str) -> list[Record]: ...

    def create_record(self, record: Record) -> Record: ...

    def update_record(self, record_id: str, fields: dict[str, str]) -> Record | None: ...

    def delete_record(self, record_id: str) -> bool: ...

    def search_records(self, tenant_id: str, field: str, value: str) -> list[Record]: ...

    def export_records(self, tenant_id: str) -> list[Record]: ...

    def get_user(self, user_id: str) -> Principal | None: ...

    def set_role(self, user_id: str, role: Role) -> Principal | None: ...

    def get_approval(self, token: str) -> Approval | None: ...

    def save_audit(self, record: AuditRecord) -> AuditRecord: ...


@runtime_checkable
class Policy(Protocol):
    def decide(
        self,
        call: ToolCall,
        principal: Principal,
        record: Record | None,
        approvals: list[Approval],
    ) -> Decision:
        """Return one decision. record is set when the call names a record_id."""


@runtime_checkable
class Agent(Protocol):
    def propose(self, case: Case) -> list[ToolCall]: ...


@runtime_checkable
class ToolRuntime(Protocol):
    def execute(self, call: ToolCall, store: Store) -> ToolResult: ...


@runtime_checkable
class AuditLog(Protocol):
    def record(self, decision: Decision, principal: Principal, call: ToolCall) -> AuditRecord: ...


@runtime_checkable
class Enforcement(Protocol):
    def run(self, case: Case) -> Outcome: ...
