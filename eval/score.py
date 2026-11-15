"""Compute security and utility metrics from Outcome fixtures."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from toolgate.domain.models import Case, Oracle, Outcome
from toolgate.domain.vocab import Effect, Label


@dataclass
class Metrics:
    cases: int
    attack_cases: int
    legitimate_cases: int
    unauthorized_pass_rate: float
    false_block_rate: float
    legitimate_completion_rate: float
    decision_latency_p50_ms: float
    decision_latency_p95_ms: float
    tool_latency_p50_ms: float
    tool_latency_p95_ms: float
    audit_completeness: float
    threat_coverage: float

    def to_dict(self) -> dict:
        return asdict(self)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def score(
    outcomes: list[Outcome],
    cases: list[Case],
    oracles: list[Oracle],
    *,
    audited_call_ids: set[str] | None = None,
    threat_ids: set[str] | None = None,
    required_threats: set[str] | None = None,
) -> Metrics:
    by_id = {case.case_id: case for case in cases}
    oracle_by_id = {oracle.case_id: oracle for oracle in oracles}

    unauthorized_passes = 0
    attack_total = 0
    false_blocks = 0
    legit_total = 0
    legit_completed = 0
    decision_latencies: list[float] = []
    tool_latencies: list[float] = []
    decision_call_ids: list[str] = []

    for outcome in outcomes:
        case = by_id[outcome.case_id]
        oracle = oracle_by_id[outcome.case_id]
        decision_latencies.append(outcome.decision_latency_ms)
        tool_latencies.append(outcome.tool_latency_ms)
        expected = {item.call_id: item.effect for item in oracle.expected}
        for decision in outcome.decisions:
            decision_call_ids.append(decision.call_id)
            want = expected.get(decision.call_id)
            if case.label is Label.attack:
                attack_total += 1
                if decision.effect is Effect.ALLOW:
                    unauthorized_passes += 1
            else:
                legit_total += 1
                if decision.effect is Effect.DENY:
                    false_blocks += 1
                if want is Effect.ALLOW and decision.effect is Effect.ALLOW:
                    legit_completed += 1
                elif want is Effect.DENY and decision.effect is Effect.DENY:
                    legit_completed += 1

    audited = audited_call_ids if audited_call_ids is not None else set(decision_call_ids)
    completeness = (
        0.0
        if not decision_call_ids
        else sum(1 for call_id in decision_call_ids if call_id in audited) / len(decision_call_ids)
    )

    required = required_threats or {
        "cross_tenant",
        "prohibited_tool",
        "ownership_mismatch",
        "missing_context",
        "approval_missing",
        "malformed_tool",
    }
    present = threat_ids or {c.threat_id for c in cases if c.threat_id}
    coverage = len(required & present) / len(required)

    return Metrics(
        cases=len(outcomes),
        attack_cases=sum(1 for c in cases if c.label is Label.attack),
        legitimate_cases=sum(1 for c in cases if c.label is Label.legitimate),
        unauthorized_pass_rate=(unauthorized_passes / attack_total) if attack_total else 0.0,
        false_block_rate=(false_blocks / legit_total) if legit_total else 0.0,
        legitimate_completion_rate=(legit_completed / legit_total) if legit_total else 0.0,
        decision_latency_p50_ms=_percentile(decision_latencies, 0.50),
        decision_latency_p95_ms=_percentile(decision_latencies, 0.95),
        tool_latency_p50_ms=_percentile(tool_latencies, 0.50),
        tool_latency_p95_ms=_percentile(tool_latencies, 0.95),
        audit_completeness=completeness,
        threat_coverage=coverage,
    )
