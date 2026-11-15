"""Build and optionally persist AuditRecord rows."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import count

from toolgate.domain.models import AuditRecord, Decision, Principal, ToolCall
from toolgate.domain.protocols import Store


class AuditService:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store
        self._ids = count(1)
        self.rows: list[AuditRecord] = []

    def record(self, decision: Decision, principal: Principal, call: ToolCall) -> AuditRecord:
        row = AuditRecord(
            audit_id=f"aud_{next(self._ids)}",
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
        if self.store is not None:
            self.store.save_audit(row)
        return row
