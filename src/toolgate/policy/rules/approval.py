"""Deny high-risk tools without a matching approval."""

from datetime import datetime, timezone

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import APPROVAL_REQUIRED, Effect, RuleId, ToolName


def _bound_resource(call: ToolCall) -> str | None:
    if call.name is ToolName.delete_record:
        value = call.arguments.get("record_id")
    elif call.name is ToolName.export_records:
        value = call.arguments.get("tenant_id")
    elif call.name is ToolName.change_permissions:
        value = call.arguments.get("user_id")
    else:
        value = None
    return value if isinstance(value, str) and value else None


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    if call.name not in APPROVAL_REQUIRED:
        return None

    token = call.arguments.get("approval_token")
    if not isinstance(token, str) or not token:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.approval,
            reason="approval_token is required",
        )

    now = datetime.now(timezone.utc)
    for approval in approvals:
        if approval.token != token:
            continue
        if approval.tool_name is not call.name:
            continue
        if approval.user_id != principal.user_id:
            continue
        if approval.expires_at is not None and approval.expires_at <= now:
            continue
        if approval.consumed_at is not None:
            return Decision(
                call_id=call.call_id,
                effect=Effect.DENY,
                rule_id=RuleId.approval,
                reason="approval token was already used",
            )
        resource = _bound_resource(call)
        if approval.resource_id is None or approval.resource_id != resource:
            continue
        del record
        return None

    return Decision(
        call_id=call.call_id,
        effect=Effect.DENY,
        rule_id=RuleId.approval,
        reason="no matching approval for this tool call",
    )
