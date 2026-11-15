"""Deny when a mutating call targets a record the principal does not own."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import Effect, Role, RuleId, ToolName

OWNERSHIP_TOOLS = frozenset(
    {
        ToolName.update_record,
        ToolName.delete_record,
        ToolName.create_record,
    }
)


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    del approvals
    if call.name not in OWNERSHIP_TOOLS:
        return None
    if principal.role is Role.admin:
        return None

    if call.name is ToolName.create_record:
        owner_id = call.arguments.get("owner_id")
        if owner_id != principal.user_id:
            return Decision(
                call_id=call.call_id,
                effect=Effect.DENY,
                rule_id=RuleId.ownership,
                reason="create_record owner_id must match principal",
            )
        return None

    if record is None:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.ownership,
            reason="record not found for ownership check",
        )
    if record.owner_id != principal.user_id:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.ownership,
            reason="principal does not own the record",
        )
    return None
