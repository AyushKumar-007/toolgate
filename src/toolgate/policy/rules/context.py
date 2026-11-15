"""Deny when principal identity is incomplete."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import Effect, RuleId


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    del record, approvals
    if not principal.user_id or not principal.tenant_id or principal.role is None:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.context,
            reason="principal is missing user, tenant, or role",
        )
    return None
