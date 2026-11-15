#!/usr/bin/env python3
"""Run recorded cases through the gateway."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from toolgate.agent.mock import MockAgent
from toolgate.agent.ollama import OllamaAgent
from toolgate.domain.models import Case
from toolgate.domain.vocab import Mode
from toolgate.enforcement.mode import ModeEnforcement
from toolgate.store.seed import seed_store
from toolgate.store.sqlite import SqliteStore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = [
    ROOT / "data" / "cases" / "legitimate" / "case_legit_read.json",
    ROOT / "data" / "cases" / "attack" / "case_cross_tenant.json",
]


def build_agent(kind: str, model: str) -> MockAgent | OllamaAgent:
    if kind == "mock":
        return MockAgent()
    if kind == "ollama":
        return OllamaAgent(model=model)
    raise SystemExit(f"unknown agent: {kind}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run recorded cases through the gateway")
    parser.add_argument("--agent", choices=("mock", "ollama"), default="mock")
    parser.add_argument("--model", default="qwen2.5:3b-instruct", help="Ollama model name")
    parser.add_argument(
        "--mode",
        choices=[m.value for m in Mode],
        default=Mode.gateway.value,
    )
    parser.add_argument(
        "--case",
        action="append",
        type=Path,
        help="Case JSON path (repeatable). Defaults to a legitimate read and a cross-tenant read.",
    )
    args = parser.parse_args(argv)

    paths = args.case or DEFAULT_CASES
    agent = build_agent(args.agent, args.model)
    mode = Mode(args.mode)

    for path in paths:
        case = Case.model_validate_json(path.read_text(encoding="utf-8"))
        store = SqliteStore(":memory:")
        seed_store(store)
        outcome = ModeEnforcement(mode, store, agent=agent).run(case)
        print(f"=== {case.case_id} ({mode.value}, agent={args.agent}) ===")
        print(json.dumps(outcome.model_dump(mode="json"), indent=2))
        print()


if __name__ == "__main__":
    main()
