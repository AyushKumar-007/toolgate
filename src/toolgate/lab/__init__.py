"""Interface: an Ollama agent proposes tool calls, and toolgate decides before execution."""

from toolgate.lab.service import (
    LabEnforceRequest,
    LabProposeResponse,
    LabRunRequest,
    LabRunResponse,
    LabService,
)

__all__ = [
    "LabService",
    "LabRunRequest",
    "LabRunResponse",
    "LabProposeResponse",
    "LabEnforceRequest",
]
