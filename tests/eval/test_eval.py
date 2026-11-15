from eval.loader import load_suite, threat_ids
from eval.score import score
from toolgate.domain.models import Decision, Outcome, Principal, ToolCall, ToolResult
from toolgate.domain.vocab import Effect, Label, Mode, Role, RuleId, ToolName, ToolStatus
from toolgate.policy import PolicyEngine


REQUIRED_CASE_THREATS = {
    "cross_tenant",
    "prohibited_tool",
    "ownership_mismatch",
    "approval_missing",
    "malformed_tool",
}


def test_suite_covers_threats_and_legitimates() -> None:
    suite = load_suite()
    assert len(suite) >= 8
    labels = {case.label for case, _ in suite}
    assert Label.legitimate in labels
    assert Label.attack in labels
    assert REQUIRED_CASE_THREATS <= threat_ids()


def test_missing_context_covered_by_policy_unit() -> None:
    principal = Principal.model_construct(user_id="", tenant_id="ten_a", role=Role.reader)
    call = ToolCall(call_id="c", name=ToolName.list_records, arguments={"tenant_id": "ten_a"})
    decision = PolicyEngine().decide(call, principal, None, [])
    assert decision.rule_id is RuleId.context
    assert decision.effect is Effect.DENY


def test_score_on_outcome_fixtures() -> None:
    suite = load_suite()
    cases = [case for case, _ in suite]
    oracles = [oracle for _, oracle in suite]
    outcomes: list[Outcome] = []
    for case, oracle in suite:
        decisions = [
            Decision(
                call_id=item.call_id,
                effect=item.effect,
                rule_id=RuleId.default if item.effect is Effect.ALLOW else RuleId.tenant,
                reason="fixture",
            )
            for item in oracle.expected
        ]
        results = [
            ToolResult(call_id=d.call_id, status=ToolStatus.ok, payload={})
            for d in decisions
            if d.effect is Effect.ALLOW
        ]
        outcomes.append(
            Outcome(
                case_id=case.case_id,
                mode=Mode.gateway,
                decisions=decisions,
                results=results,
                executed_call_ids=[d.call_id for d in decisions if d.effect is Effect.ALLOW],
                decision_latency_ms=1.0,
                tool_latency_ms=2.0,
            )
        )

    metrics = score(
        outcomes,
        cases,
        oracles,
        audited_call_ids={d.call_id for o in outcomes for d in o.decisions},
        threat_ids=threat_ids(),
        required_threats=REQUIRED_CASE_THREATS,
    )
    assert metrics.unauthorized_pass_rate == 0.0
    assert metrics.false_block_rate == 0.0
    assert metrics.legitimate_completion_rate == 1.0
    assert metrics.audit_completeness == 1.0
    assert metrics.threat_coverage == 1.0
