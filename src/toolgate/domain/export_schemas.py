"""Write JSON Schema files from the Pydantic models."""

import json
import sys
from pathlib import Path

from toolgate.domain.models import (
    Approval,
    AuditRecord,
    Case,
    Decision,
    Oracle,
    Outcome,
    Principal,
    Record,
    ToolCall,
    ToolResult,
)

SCHEMA_MODELS: dict[str, type] = {
    "principal": Principal,
    "tool_call": ToolCall,
    "record": Record,
    "approval": Approval,
    "decision": Decision,
    "tool_result": ToolResult,
    "audit_record": AuditRecord,
    "case": Case,
    "oracle": Oracle,
    "outcome": Outcome,
}


def export_schemas(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMA_MODELS.items():
        payload = model.model_json_schema()
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        (directory / f"{name}.schema.json").write_text(text)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    target = Path(args[0]) if args else Path.cwd() / "schemas"
    export_schemas(target)


if __name__ == "__main__":
    main()
