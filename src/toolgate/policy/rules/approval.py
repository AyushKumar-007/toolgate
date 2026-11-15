"""Deny high-risk tools without a matching approval."""

from datetime import datetime, timezone

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import APPROVAL_REQUIRED, Effect, RuleId, ToolName


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
        if call.name is ToolName.delete_record:
            resource = call.arguments.get("record_id")
            if approval.resource_id not in (None, resource):
                continue
        if call.name is ToolName.export_records:
            resource = call.arguments.get("tenant_id")
            if approval.resource_id not in (None, resource):
                continue
        if call.name is ToolName.change_permissions:
            resource = call.arguments.get("user_id")
            if approval.resource_id not in (None, resource):
                continue
        del record
        return None

    return Decision(
        call_id=call.call_id,
        effect=Effect.DENY,
        rule_id=RuleId.approval,
        reason="no matching approval for this tool call",
    )
