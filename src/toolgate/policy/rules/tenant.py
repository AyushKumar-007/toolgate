"""Deny cross-tenant access."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import Effect, RuleId, ToolName


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    del approvals
    if call.name in {
        ToolName.read_record,
        ToolName.update_record,
        ToolName.delete_record,
    }:
        if record is None:
            return Decision(
                call_id=call.call_id,
                effect=Effect.DENY,
                rule_id=RuleId.tenant,
                reason="record not found for tenant check",
            )
        if record.tenant_id != principal.tenant_id:
            return Decision(
                call_id=call.call_id,
                effect=Effect.DENY,
                rule_id=RuleId.tenant,
                reason="record tenant does not match principal",
            )
        return None

    tenant_arg = call.arguments.get("tenant_id")
    if isinstance(tenant_arg, str) and tenant_arg != principal.tenant_id:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.tenant,
            reason="argument tenant_id does not match principal",
        )
    return None
