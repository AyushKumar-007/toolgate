"""Deny tools outside the role allow-list."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import ROLE_ACTIONS, Effect, RuleId


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    del record, approvals
    allowed = ROLE_ACTIONS[principal.role]
    if call.name not in allowed:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.actions,
            reason=f"role {principal.role.value} cannot call {call.name.value}",
        )
    return None
