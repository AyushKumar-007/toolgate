"""Deterministic agent: replay proposals from the case file."""

from toolgate.domain.models import Case, ToolCall


class MockAgent:
    def propose(self, case: Case) -> list[ToolCall]:
        return list(case.proposals)
