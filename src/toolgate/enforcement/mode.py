"""Wire agent, policy, tools, and audit into the three baseline modes."""

from __future__ import annotations

import time

from toolgate.agent.mock import MockAgent
from toolgate.audit.service import AuditService
from toolgate.domain.models import Approval, Case, Decision, Outcome, Record, ToolCall
from toolgate.domain.protocols import Agent, AuditLog, Policy, Store, ToolRuntime
from toolgate.domain.vocab import Effect, Mode, RuleId
from toolgate.policy.engine import PolicyEngine
from toolgate.tools.runtime import SimulatedRuntime


class ModeEnforcement:
    def __init__(
        self,
        mode: Mode,
        store: Store,
        *,
        agent: Agent | None = None,
        policy: Policy | None = None,
        runtime: ToolRuntime | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self.mode = mode
        self.store = store
        self.agent = agent or MockAgent()
        self.policy = policy or PolicyEngine()
        self.runtime = runtime or SimulatedRuntime()
        self.audit = audit or AuditService(store)

    def run(self, case: Case) -> Outcome:
        proposals = self.agent.propose(case)
        decisions: list[Decision] = []
        results = []
        executed: list[str] = []
        decision_ms = 0.0
        tool_ms = 0.0

        for call in proposals:
            started = time.perf_counter()
            decision = self._decide(case, call)
            decision_ms += (time.perf_counter() - started) * 1000.0
            self.audit.record(decision, case.principal, call)
            decisions.append(decision)

            if decision.effect is Effect.ALLOW:
                started = time.perf_counter()
                result = self.runtime.execute(call, self.store)
                tool_ms += (time.perf_counter() - started) * 1000.0
                results.append(result)
                executed.append(call.call_id)

        return Outcome(
            case_id=case.case_id,
            mode=self.mode,
            decisions=decisions,
            results=results,
            executed_call_ids=executed,
            decision_latency_ms=decision_ms,
            tool_latency_ms=tool_ms,
        )

    def _decide(self, case: Case, call: ToolCall) -> Decision:
        if self.mode is Mode.direct:
            return Decision(
                call_id=call.call_id,
                effect=Effect.ALLOW,
                rule_id=RuleId.direct,
                reason="direct mode executes the proposal",
            )
        if self.mode is Mode.prompt_only:
            effect = Effect.ALLOW if case.prompt_only_would_execute else Effect.DENY
            return Decision(
                call_id=call.call_id,
                effect=effect,
                rule_id=RuleId.prompt_only,
                reason="prompt-only baseline uses case.prompt_only_would_execute",
            )
        record = self._load_record(call)
        approvals = self._load_approvals(call)
        return self.policy.decide(call, case.principal, record, approvals)

    def _load_record(self, call: ToolCall) -> Record | None:
        record_id = call.arguments.get("record_id")
        if not isinstance(record_id, str):
            return None
        return self.store.get_record(record_id)

    def _load_approvals(self, call: ToolCall) -> list[Approval]:
        token = call.arguments.get("approval_token")
        if not isinstance(token, str):
            return []
        approval = self.store.get_approval(token)
        return [approval] if approval is not None else []


def build_enforcement(mode: Mode, store: Store, **kwargs: object) -> ModeEnforcement:
    return ModeEnforcement(mode, store, **kwargs)  # type: ignore[arg-type]
