"""Ordered policy evaluation. First deny wins; otherwise ALLOW."""

from toolgate.domain.models import Approval, Decision, Principal, Record, ToolCall
from toolgate.domain.vocab import Effect, RuleId
from toolgate.policy.rules import actions, approval, arguments, context, ownership, schema, tenant

RULES = (
    context.check,
    schema.check,
    tenant.check,
    ownership.check,
    actions.check,
    arguments.check,
    approval.check,
)


class PolicyEngine:
    def decide(
        self,
        call: ToolCall,
        principal: Principal,
        record: Record | None,
        approvals: list[Approval],
    ) -> Decision:
        for rule in RULES:
            decision = rule(call, principal, record, approvals)
            if decision is None:
                continue
            if not decision.call_id:
                decision = decision.model_copy(update={"call_id": call.call_id})
            return decision
        return Decision(
            call_id=call.call_id,
            effect=Effect.ALLOW,
            rule_id=RuleId.default,
            reason="all policy checks passed",
        )
