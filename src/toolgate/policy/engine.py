"""Ordered policy evaluation. First deny wins; otherwise ALLOW."""

from typing import Any

from pydantic import ValidationError

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

    def admit(
        self,
        raw_call: dict[str, Any],
        raw_principal: dict[str, Any],
        record: Record | None,
        approvals: list[Approval],
    ) -> Decision:
        """Deny incomplete identity or an unparsable call before the ordered rules."""
        call_id = str(raw_call.get("call_id") or "unparsed")
        user_id = raw_principal.get("user_id") if isinstance(raw_principal, dict) else None
        tenant_id = raw_principal.get("tenant_id") if isinstance(raw_principal, dict) else None
        role = raw_principal.get("role") if isinstance(raw_principal, dict) else None
        if not user_id or not tenant_id or not role:
            return Decision(
                call_id=call_id,
                effect=Effect.DENY,
                rule_id=RuleId.context,
                reason="principal is missing user, tenant, or role",
            )
        try:
            principal = Principal.model_validate(raw_principal)
        except ValidationError:
            return Decision(
                call_id=call_id,
                effect=Effect.DENY,
                rule_id=RuleId.context,
                reason="principal is missing user, tenant, or role",
            )
        try:
            call = ToolCall.model_validate(raw_call)
        except ValidationError as exc:
            text = str(exc)
            rule = RuleId.arguments if "missing arguments" in text else RuleId.schema
            return Decision(
                call_id=call_id,
                effect=Effect.DENY,
                rule_id=rule,
                reason="tool call could not be parsed",
            )
        return self.decide(call, principal, record, approvals)
