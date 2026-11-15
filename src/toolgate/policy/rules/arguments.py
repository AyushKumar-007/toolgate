"""Argument-level constraints beyond schema shape."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import Effect, RuleId, ToolName


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    del principal, record, approvals
    if call.name is ToolName.update_record:
        fields = call.arguments.get("fields")
        if not isinstance(fields, dict) or not fields:
            return Decision(
                call_id=call.call_id,
                effect=Effect.DENY,
                rule_id=RuleId.arguments,
                reason="update_record fields must be a non-empty object",
            )
    if call.name is ToolName.export_records:
        # Keep export scoped to a single tenant argument (already required).
        tenant_id = call.arguments.get("tenant_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            return Decision(
                call_id=call.call_id,
                effect=Effect.DENY,
                rule_id=RuleId.arguments,
                reason="export_records requires a tenant_id",
            )
    return None
