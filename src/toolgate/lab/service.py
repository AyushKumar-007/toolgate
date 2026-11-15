"""Orchestrate a live Ollama agent run through toolgate in staged phases."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from toolgate.agent.mock import MockAgent
from toolgate.agent.ollama import OllamaAgent, ping_ollama
from toolgate.domain.models import Case, Outcome, Principal, ToolCall
from toolgate.domain.protocols import AuditLog
from toolgate.domain.vocab import Effect, Label, Mode, ToolName
from toolgate.enforcement.mode import ModeEnforcement
from toolgate.lab.presets import PRESETS
from toolgate.store.sqlite import SqliteStore


class LabEvent(BaseModel):
    stage: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class LabRunRequest(BaseModel):
    task: str = Field(min_length=1)
    principal: Principal
    mode: Mode = Mode.gateway
    model: str | None = None
    preset_id: str | None = None
    allow_fallback: bool = True
    run_id: str | None = None


class LabProposeResponse(BaseModel):
    run_id: str
    status: Literal["calling"] = "calling"
    agent_backend: Literal["ollama", "fallback"]
    model: str
    task: str
    principal: Principal
    proposals: list[ToolCall]
    events: list[LabEvent]
    agent_raw: dict[str, Any] = Field(default_factory=dict)
    misuse_note: str | None = None


class LabEnforceRequest(BaseModel):
    run_id: str = Field(min_length=1)
    task: str = Field(min_length=1)
    principal: Principal
    mode: Mode = Mode.gateway
    proposals: list[ToolCall] = Field(min_length=1)
    agent_backend: Literal["ollama", "fallback"] = "ollama"
    model: str = "ollama"
    preset_id: str | None = None
    agent_raw: dict[str, Any] = Field(default_factory=dict)
    events: list[LabEvent] = Field(default_factory=list)
    reveal: bool = True


class LabRunResponse(BaseModel):
    run_id: str
    agent_backend: Literal["ollama", "fallback"]
    model: str
    task: str
    principal: Principal
    proposals: list[ToolCall]
    outcome: Outcome
    events: list[LabEvent]
    agent_raw: dict[str, Any] = Field(default_factory=dict)
    misuse_note: str | None = None
    store_snapshot: dict[str, Any] = Field(default_factory=dict)


MISUSE_NOTES = {
    "lab_attack_cross_tenant": (
        "Blocked cross-tenant disclosure: Tenant A cannot read Tenant B records."
    ),
    "lab_attack_delete": (
        "Blocked privilege abuse: a reader cannot execute delete_record."
    ),
    "lab_attack_export": (
        "Blocked unapproved bulk export: forged approval tokens are rejected."
    ),
    "lab_attack_escalate": (
        "Blocked privilege escalation: readers cannot call change_permissions."
    ),
}


def _note_for_outcome(
    *,
    preset_id: str | None,
    principal: Principal,
    outcome: Outcome | None,
) -> str | None:
    """Prefer the real deny reason over a stale attack-preset caption."""
    decision = outcome.decisions[0] if outcome and outcome.decisions else None
    if decision is not None and decision.effect is Effect.DENY:
        if decision.rule_id.value == "tenant" and "not found" in decision.reason:
            return (
                "Target record is missing (often already deleted). "
                "The live lab reseeds before each run · retry the admin delete preset."
            )
        if decision.rule_id.value == "actions":
            return f"Blocked privilege check: {decision.reason}"
        if decision.rule_id.value == "approval":
            return f"Blocked approval check: {decision.reason}"
        if decision.rule_id.value == "tenant":
            return f"Blocked tenant isolation: {decision.reason}"
        if decision.rule_id.value == "ownership":
            return f"Blocked ownership check: {decision.reason}"
        return f"Denied by rule {decision.rule_id.value}: {decision.reason}"

    # Attack captions only make sense when the principal still matches the story.
    if preset_id == "lab_attack_delete" and principal.role.value != "reader":
        return None
    return MISUSE_NOTES.get(preset_id or "")


class LabService:
    def __init__(
        self,
        store: SqliteStore,
        *,
        audit: AuditLog | None = None,
        default_model: str = "qwen2.5:3b-instruct",
        base_url: str = "http://127.0.0.1:11434",
    ) -> None:
        self.store = store
        self.audit = audit
        self.default_model = default_model
        self.base_url = base_url

    def status(self) -> dict[str, Any]:
        ping = ping_ollama(self.base_url)
        models = ping.get("models") or []
        preferred = self.default_model if self.default_model in models else (
            models[0] if models else self.default_model
        )
        return {
            "ollama_ok": bool(ping.get("ok")),
            "error": ping.get("error"),
            "models": models,
            "preferred_model": preferred,
            "tools": [name.value for name in ToolName],
            "presets": PRESETS,
            "principals": [
                {"user_id": "usr_ana", "tenant_id": "ten_a", "role": "reader"},
                {"user_id": "usr_ben", "tenant_id": "ten_b", "role": "editor"},
                {"user_id": "usr_cara", "tenant_id": "ten_a", "role": "admin"},
            ],
        }

    def propose(self, request: LabRunRequest) -> LabProposeResponse:
        run_id = request.run_id or f"lab_{uuid.uuid4().hex[:10]}"
        model = request.model or self.default_model
        preset = next((p for p in PRESETS if p["id"] == request.preset_id), None)

        events = [
            LabEvent(
                stage="user",
                message="Authenticated principal enters the live lab",
                detail=request.principal.model_dump(mode="json"),
            ),
            LabEvent(
                stage="agent_think",
                message=f"Ollama agent ({model}) is proposing a tool call",
                detail={"task": request.task, "backend": "ollama"},
            ),
        ]

        placeholder = ToolCall(
            call_id="pending",
            name=ToolName.list_records,
            arguments={"tenant_id": request.principal.tenant_id},
        )
        case = Case(
            case_id=run_id,
            label=Label.attack if preset and preset.get("kind") == "attack" else Label.legitimate,
            threat_id="lab_live" if preset and preset.get("kind") == "attack" else None,
            task=request.task,
            principal=request.principal,
            proposals=[placeholder],
            prompt_only_would_execute=True,
        )

        agent = OllamaAgent(model=model, base_url=self.base_url)
        backend: Literal["ollama", "fallback"] = "ollama"
        proposals: list[ToolCall]
        raw: dict[str, Any] = {}

        try:
            started = time.perf_counter()
            proposals = agent.propose(case)
            latency_ms = (time.perf_counter() - started) * 1000.0
            raw = agent.last_raw or {}
            events.append(
                LabEvent(
                    stage="agent_propose",
                    message="Agent decided to call a tool",
                    detail={
                        "latency_ms": round(latency_ms, 1),
                        "proposals": [p.model_dump(mode="json") for p in proposals],
                        "raw": raw,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            if not request.allow_fallback or not preset or "fallback_proposal" not in preset:
                raise
            backend = "fallback"
            proposals = [ToolCall.model_validate(preset["fallback_proposal"])]
            raw = {"fallback_reason": str(exc), "source": "preset_fallback"}
            events.append(
                LabEvent(
                    stage="agent_propose",
                    message="Fallback adversarial proposal selected",
                    detail={
                        "error": str(exc),
                        "proposals": [p.model_dump(mode="json") for p in proposals],
                    },
                )
            )

        return LabProposeResponse(
            run_id=run_id,
            agent_backend=backend,
            model=model if backend == "ollama" else f"{model} (fallback)",
            task=request.task,
            principal=request.principal,
            proposals=proposals,
            events=events,
            agent_raw=raw,
            misuse_note=_note_for_outcome(
                preset_id=request.preset_id,
                principal=request.principal,
                outcome=None,
            ),
        )

    def enforce(self, request: LabEnforceRequest) -> LabRunResponse:
        preset = next((p for p in PRESETS if p["id"] == request.preset_id), None)
        case = Case(
            case_id=request.run_id,
            label=Label.attack if preset and preset.get("kind") == "attack" else Label.legitimate,
            threat_id="lab_live" if preset and preset.get("kind") == "attack" else None,
            task=request.task,
            principal=request.principal,
            proposals=request.proposals,
            prompt_only_would_execute=True,
        )
        events = list(request.events)
        events.append(
            LabEvent(
                stage="enforce",
                message=f"Enforcement mode selected: {request.mode.value}",
                detail={"mode": request.mode.value},
            )
        )

        enforcement = ModeEnforcement(
            request.mode,
            self.store,
            agent=MockAgent(),
            audit=self.audit,
        )
        outcome = enforcement.run(case)

        for decision in outcome.decisions:
            events.append(
                LabEvent(
                    stage="policy",
                    message=f"Policy decision {decision.effect.value} via {decision.rule_id.value}",
                    detail=decision.model_dump(mode="json"),
                )
            )
            events.append(
                LabEvent(
                    stage="decision",
                    message=f"{decision.effect.value} · {decision.rule_id.value} · {decision.reason}",
                    detail=decision.model_dump(mode="json"),
                )
            )
            events.append(
                LabEvent(
                    stage="audit",
                    message="Decision appended to the audit log",
                    detail={"call_id": decision.call_id, "effect": decision.effect.value},
                )
            )
            if decision.effect is Effect.ALLOW:
                events.append(
                    LabEvent(
                        stage="tools",
                        message="Tool runtime executed · side effects applied",
                        detail={
                            "results": [r.model_dump(mode="json") for r in outcome.results]
                        },
                    )
                )
            else:
                events.append(
                    LabEvent(
                        stage="blocked",
                        message="Tool runtime skipped · no side effects",
                        detail={"rule_id": decision.rule_id.value},
                    )
                )

        return LabRunResponse(
            run_id=request.run_id,
            agent_backend=request.agent_backend,
            model=request.model,
            task=request.task,
            principal=request.principal,
            proposals=request.proposals,
            outcome=outcome,
            events=events,
            agent_raw=request.agent_raw,
            misuse_note=_note_for_outcome(
                preset_id=request.preset_id,
                principal=request.principal,
                outcome=outcome,
            ),
            store_snapshot=self._snapshot(),
        )

    def run(self, request: LabRunRequest) -> LabRunResponse:
        proposed = self.propose(request)
        return self.enforce(
            LabEnforceRequest(
                run_id=proposed.run_id,
                task=proposed.task,
                principal=proposed.principal,
                mode=request.mode,
                proposals=proposed.proposals,
                agent_backend=proposed.agent_backend,
                model=proposed.model,
                preset_id=request.preset_id,
                agent_raw=proposed.agent_raw,
                events=proposed.events,
            )
        )

    def _snapshot(self) -> dict[str, Any]:
        records = []
        for tenant in ("ten_a", "ten_b"):
            records.extend(
                r.model_dump(mode="json") for r in self.store.list_records(tenant)
            )
        return {"records": records, "record_count": len(records)}
