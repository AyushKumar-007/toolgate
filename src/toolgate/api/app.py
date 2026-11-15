"""HTTP API: run tasks, list audits, register approvals, and serve the project interface."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from eval.loader import load_suite
from toolgate.audit.service import AuditService
from toolgate.domain.models import Approval, AuditRecord, Case, Outcome
from toolgate.domain.vocab import GET_AUDIT, Mode, POST_APPROVALS, POST_TASKS
from toolgate.enforcement.mode import ModeEnforcement
from toolgate.lab.desktop_spawn import close_companions, spawn_window
from toolgate.lab.service import (
    LabEnforceRequest,
    LabProposeResponse,
    LabRunRequest,
    LabRunResponse,
    LabService,
)
from toolgate.store.seed import seed_store
from toolgate.store.sqlite import SqliteStore

WEB_DIR = Path(__file__).resolve().parent / "web"
BASE = "http://127.0.0.1:8000"


class AppState:
    def __init__(self, store: SqliteStore | None = None) -> None:
        self.store = store or SqliteStore(":memory:")
        self._owned_store = store is None
        if store is None:
            seed_store(self.store)
        self.audit = AuditService(self.store)
        self.lab = LabService(self.store, audit=self.audit)
        self.latest_lab: dict[str, Any] | None = None

    def reset(self) -> None:
        """Re-seed a fresh in-memory store for user-study sessions."""
        if not self._owned_store:
            raise RuntimeError("cannot reset an externally supplied store")
        self.store.close()
        self.store = SqliteStore(":memory:")
        seed_store(self.store)
        self.audit = AuditService(self.store)
        self.lab = LabService(self.store, audit=self.audit)
        self.latest_lab = None

    def enforcement(self, mode: Mode) -> ModeEnforcement:
        return ModeEnforcement(mode, self.store, audit=self.audit)

    def publish_lab(self, payload: dict[str, Any]) -> None:
        self.latest_lab = payload


def create_app(state: AppState | None = None) -> FastAPI:
    app_state = state or AppState()
    app = FastAPI(title="toolgate", version="0.4.0")
    app.state.toolgate = app_state
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def home() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/lab/agent")
    def agent_desktop_ui() -> FileResponse:
        return FileResponse(WEB_DIR / "agent.html")

    @app.get("/lab/tools")
    def tools_desktop_ui() -> FileResponse:
        return FileResponse(WEB_DIR / "tools.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.4.0"}

    @app.get("/modes")
    def list_modes() -> dict[str, list[str]]:
        return {"modes": [mode.value for mode in Mode]}

    @app.get("/cases", response_model=list[Case])
    def list_cases() -> list[Case]:
        return [case for case, _ in load_suite()]

    @app.get("/lab/status")
    def lab_status() -> dict:
        return app_state.lab.status()

    @app.get("/lab/latest")
    def lab_latest() -> dict:
        if app_state.latest_lab is None:
            return {"run_id": None, "status": "idle"}
        return app_state.latest_lab

    @app.post("/lab/desktop/close")
    def lab_desktop_close() -> dict:
        return close_companions()

    @app.post("/lab/desktop/agent")
    def lab_desktop_agent() -> dict:
        try:
            return spawn_window("agent", BASE, force=True)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/lab/desktop/tools")
    def lab_desktop_tools() -> dict:
        try:
            return spawn_window("tools", BASE, force=True)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    def _empty_outcome(run_id: str, mode: Mode) -> dict:
        return {
            "case_id": run_id,
            "mode": mode.value,
            "decisions": [],
            "results": [],
            "executed_call_ids": [],
            "decision_latency_ms": 0,
            "tool_latency_ms": 0,
        }

    @app.post("/lab/thinking")
    def lab_thinking(body: LabRunRequest) -> dict:
        """Publish thinking state before Ollama is called (for desktop animation)."""
        run_id = body.run_id or f"lab_{uuid.uuid4().hex[:10]}"
        model = body.model or app_state.lab.default_model
        payload = {
            "run_id": run_id,
            "status": "thinking",
            "agent_backend": "ollama",
            "model": model,
            "task": body.task,
            "principal": body.principal.model_dump(mode="json"),
            "proposals": [],
            "outcome": _empty_outcome(run_id, body.mode),
            "events": [
                {
                    "stage": "agent_think",
                    "message": f"Ollama agent ({model}) is thinking…",
                    "detail": {"task": body.task},
                }
            ],
            "agent_raw": {},
            "misuse_note": None,
            "store_snapshot": {},
        }
        app_state.publish_lab(payload)
        return payload

    @app.post("/lab/propose", response_model=LabProposeResponse)
    def lab_propose(body: LabRunRequest) -> LabProposeResponse:
        try:
            proposed = app_state.lab.propose(body)
            payload = proposed.model_dump(mode="json")
            payload["status"] = "calling"
            payload["outcome"] = _empty_outcome(proposed.run_id, body.mode)
            payload["store_snapshot"] = {}
            app_state.publish_lab(payload)
            return proposed
        except ConnectionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/lab/enforce", response_model=LabRunResponse)
    def lab_enforce(body: LabEnforceRequest) -> LabRunResponse:
        # Keep status=evaluating until the control UI reveals the verdict.
        pending = dict(app_state.latest_lab or {})
        pending.update(
            {
                "run_id": body.run_id,
                "status": "evaluating",
                "task": body.task,
                "principal": body.principal.model_dump(mode="json"),
                "proposals": [p.model_dump(mode="json") for p in body.proposals],
                "agent_backend": body.agent_backend,
                "model": body.model,
            }
        )
        app_state.publish_lab(pending)
        try:
            result = app_state.lab.enforce(body)
            payload = result.model_dump(mode="json")
            payload["status"] = "done" if body.reveal else "evaluating"
            app_state.publish_lab(payload)
            return result
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/lab/reveal")
    def lab_reveal() -> dict:
        """Flip latest lab status to done so Tools desktop shows ALLOW/DENY."""
        if not app_state.latest_lab:
            raise HTTPException(status_code=404, detail="no lab run to reveal")
        payload = dict(app_state.latest_lab)
        payload["status"] = "done"
        app_state.publish_lab(payload)
        return payload

    @app.post("/lab/run", response_model=LabRunResponse)
    def lab_run(body: LabRunRequest) -> LabRunResponse:
        """Compatibility: propose + enforce in one call."""
        run_id = body.run_id or f"lab_{uuid.uuid4().hex[:10]}"
        body = body.model_copy(update={"run_id": run_id})
        lab_thinking(body)
        proposed = lab_propose(body)
        return lab_enforce(
            LabEnforceRequest(
                run_id=proposed.run_id,
                task=proposed.task,
                principal=proposed.principal,
                mode=body.mode,
                proposals=proposed.proposals,
                agent_backend=proposed.agent_backend,
                model=proposed.model,
                preset_id=body.preset_id,
                agent_raw=proposed.agent_raw,
                events=proposed.events,
            )
        )

    @app.post("/reset")
    def reset_state() -> dict[str, str]:
        try:
            app_state.reset()
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "reset"}

    @app.post(POST_TASKS, response_model=Outcome)
    def run_task(
        case: Case,
        mode: Mode = Query(default=Mode.gateway),
    ) -> Outcome:
        return app_state.enforcement(mode).run(case)

    @app.get(GET_AUDIT, response_model=list[AuditRecord])
    def list_audit() -> list[AuditRecord]:
        return list(app_state.audit.rows)

    @app.post(POST_APPROVALS, response_model=Approval)
    def create_approval(approval: Approval) -> Approval:
        put = getattr(app_state.store, "put_approval", None)
        if put is None:
            raise HTTPException(status_code=500, detail="store cannot save approvals")
        return put(approval)

    return app
