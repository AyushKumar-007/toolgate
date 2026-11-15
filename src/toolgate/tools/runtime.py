"""Execute tool calls against a Store with no policy checks."""

from __future__ import annotations

import uuid

from toolgate.domain.models import Record, ToolCall, ToolResult
from toolgate.domain.protocols import Store
from toolgate.domain.vocab import Role, ToolName, ToolStatus


class SimulatedRuntime:
    def execute(self, call: ToolCall, store: Store) -> ToolResult:
        try:
            payload = self._dispatch(call, store)
            return ToolResult(call_id=call.call_id, status=ToolStatus.ok, payload=payload)
        except Exception as exc:  # noqa: BLE001 — surface tool errors in payload
            return ToolResult(
                call_id=call.call_id,
                status=ToolStatus.error,
                payload={"error": str(exc)},
            )

    def _dispatch(self, call: ToolCall, store: Store) -> dict:
        args = call.arguments
        if call.name is ToolName.list_records:
            records = store.list_records(args["tenant_id"])
            return {"records": [r.model_dump(mode="json") for r in records]}
        if call.name is ToolName.read_record:
            record = store.get_record(args["record_id"])
            if record is None:
                raise ValueError(f"record not found: {args['record_id']}")
            return {"record": record.model_dump(mode="json")}
        if call.name is ToolName.search_records:
            records = store.search_records(args["tenant_id"], args["field"], args["value"])
            return {"records": [r.model_dump(mode="json") for r in records]}
        if call.name is ToolName.create_record:
            record_id = args.get("record_id") or f"rec_{uuid.uuid4().hex[:8]}"
            record = Record(
                record_id=str(record_id),
                tenant_id=args["tenant_id"],
                owner_id=args["owner_id"],
                title=args["title"],
                body=args["body"],
            )
            created = store.create_record(record)
            return {"record": created.model_dump(mode="json")}
        if call.name is ToolName.update_record:
            updated = store.update_record(args["record_id"], args["fields"])
            if updated is None:
                raise ValueError(f"record not found: {args['record_id']}")
            return {"record": updated.model_dump(mode="json")}
        if call.name is ToolName.delete_record:
            deleted = store.delete_record(args["record_id"])
            if not deleted:
                raise ValueError(f"record not found: {args['record_id']}")
            return {"deleted": args["record_id"]}
        if call.name is ToolName.export_records:
            records = store.export_records(args["tenant_id"])
            return {"records": [r.model_dump(mode="json") for r in records]}
        if call.name is ToolName.change_permissions:
            updated = store.set_role(args["user_id"], Role(args["role"]))
            if updated is None:
                raise ValueError(f"user not found: {args['user_id']}")
            return {"user": updated.model_dump(mode="json")}
        raise ValueError(f"unsupported tool: {call.name}")
