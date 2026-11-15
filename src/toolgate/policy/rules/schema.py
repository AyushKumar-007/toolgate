"""Deny unexpected argument keys beyond the tool's declared fields."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import REQUIRED_ARGUMENTS, Effect, RuleId, ToolName

OPTIONAL_ARGS: dict[ToolName, frozenset[str]] = {
    ToolName.list_records: frozenset(),
    ToolName.read_record: frozenset(),
    ToolName.search_records: frozenset(),
    ToolName.create_record: frozenset(),
    ToolName.update_record: frozenset(),
    ToolName.delete_record: frozenset(),
    ToolName.export_records: frozenset(),
    ToolName.change_permissions: frozenset(),
}


def check(
    call: ToolCall,
    principal: Principal,
    record: Record | None,
    approvals: list[Approval],
) -> Decision | None:
    del principal, record, approvals
    allowed = REQUIRED_ARGUMENTS[call.name] | OPTIONAL_ARGS[call.name]
    unexpected = sorted(set(call.arguments) - allowed)
    if unexpected:
        return Decision(
            call_id=call.call_id,
            effect=Effect.DENY,
            rule_id=RuleId.schema,
            reason=f"unexpected arguments: {', '.join(unexpected)}",
        )
    return None
