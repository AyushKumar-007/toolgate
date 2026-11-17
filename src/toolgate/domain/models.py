"""Pydantic models are the stage 0 contract. JSON Schema is generated from them."""

from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from toolgate.domain.vocab import (
    RECORD_FIELDS,
    REQUIRED_ARGUMENTS,
    SEARCH_FIELDS,
    Effect,
    Label,
    Mode,
    Role,
    RuleId,
    ToolName,
    ToolStatus,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


class Principal(APIModel):
    user_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    role: Role


class Record(APIModel):
    record_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    title: str
    body: str


class Approval(APIModel):
    token: str = Field(min_length=1)
    tool_name: ToolName
    resource_id: str | None = None
    user_id: str = Field(min_length=1)
    expires_at: datetime | None = None
    consumed_at: datetime | None = None


class ToolCall(APIModel):
    call_id: str = Field(min_length=1)
    name: ToolName
    arguments: dict[str, Any]

    @model_validator(mode="after")
    def arguments_match_tool(self) -> Self:
        missing = sorted(REQUIRED_ARGUMENTS[self.name] - self.arguments.keys())
        if missing:
            raise ValueError(f"{self.name.value} missing arguments: {', '.join(missing)}")
        self._check_argument_types()
        return self

    def _check_argument_types(self) -> None:
        args = self.arguments
        for key in ("tenant_id", "record_id", "owner_id", "title", "body", "approval_token", "user_id", "value"):
            if key in args:
                _text(args[key], key)
        if "field" in args:
            field = _text(args["field"], "field")
            if field not in SEARCH_FIELDS:
                raise ValueError(f"field must be one of: {', '.join(sorted(SEARCH_FIELDS))}")
        if "role" in args:
            _text(args["role"], "role")
            Role(args["role"])
        if "fields" in args:
            fields = args["fields"]
            if not isinstance(fields, dict):
                raise ValueError("fields must be an object")
            unknown = sorted(set(fields) - RECORD_FIELDS)
            if unknown:
                raise ValueError(f"fields has unknown keys: {', '.join(unknown)}")
            for key, value in fields.items():
                if not isinstance(value, str):
                    raise ValueError(f"fields.{key} must be a string")


class Decision(APIModel):
    call_id: str = Field(min_length=1)
    effect: Effect
    rule_id: RuleId
    reason: str


class ToolResult(APIModel):
    call_id: str = Field(min_length=1)
    status: ToolStatus
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditRecord(APIModel):
    audit_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    effect: Effect
    rule_id: RuleId
    reason: str
    user_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    tool_name: ToolName
    created_at: datetime


class Case(APIModel):
    case_id: str = Field(min_length=1)
    label: Label
    threat_id: str | None = None
    task: str = Field(min_length=1)
    principal: Principal
    proposals: list[ToolCall] = Field(min_length=1)
    prompt_only_would_execute: bool

    @model_validator(mode="after")
    def threat_matches_label(self) -> Self:
        if self.label is Label.attack and not self.threat_id:
            raise ValueError("attack cases include a threat_id")
        if self.label is Label.legitimate and self.threat_id is not None:
            raise ValueError("legitimate cases leave threat_id empty")
        return self


class ExpectedEffect(APIModel):
    call_id: str = Field(min_length=1)
    effect: Effect


class Oracle(APIModel):
    case_id: str = Field(min_length=1)
    expected: list[ExpectedEffect] = Field(min_length=1)


class Outcome(APIModel):
    case_id: str = Field(min_length=1)
    mode: Mode
    decisions: list[Decision]
    results: list[ToolResult]
    executed_call_ids: list[str]
    decision_latency_ms: float = Field(ge=0)
    tool_latency_ms: float = Field(ge=0)
