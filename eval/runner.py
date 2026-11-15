"""Run the fixed case suite under all three enforcement modes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.loader import load_suite, threat_ids
from eval.score import Metrics, score
from toolgate.domain.vocab import Mode
from toolgate.enforcement.mode import ModeEnforcement
from toolgate.store.seed import seed_store
from toolgate.store.sqlite import SqliteStore

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "data" / "results"

REQUIRED_CASE_THREATS = {
    "cross_tenant",
    "prohibited_tool",
    "ownership_mismatch",
    "approval_missing",
    "malformed_tool",
}


def run_mode(mode: Mode) -> tuple[list, Metrics]:
    suite = load_suite()
    outcomes = []
    audited: set[str] = set()
    cases = []
    oracles = []

    for case, oracle in suite:
        store = SqliteStore(":memory:")
        seed_store(store)
        enforcement = ModeEnforcement(mode, store)
        outcome = enforcement.run(case)
        outcomes.append(outcome)
        cases.append(case)
        oracles.append(oracle)
        for decision in outcome.decisions:
            audited.add(decision.call_id)

    metrics = score(
        outcomes,
        cases,
        oracles,
        audited_call_ids=audited,
        threat_ids=threat_ids(),
        required_threats=REQUIRED_CASE_THREATS,
    )
    return outcomes, metrics


def write_results(
    mode: Mode,
    outcomes: list,
    metrics: Metrics,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [outcome.model_dump_json() for outcome in outcomes]
    (out_dir / f"{mode.value}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"{mode.value}.metrics.json").write_text(
        json.dumps(metrics.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )


def run_all(modes: list[Mode] | None = None, out_dir: Path | None = None) -> dict[str, Metrics]:
    target = out_dir or DEFAULT_OUT
    selected = modes or [Mode.direct, Mode.prompt_only, Mode.gateway]
    summary: dict[str, Metrics] = {}
    for mode in selected:
        outcomes, metrics = run_mode(mode)
        write_results(mode, outcomes, metrics, target)
        summary[mode.value] = metrics
    (target / "summary.json").write_text(
        json.dumps({name: m.to_dict() for name, m in summary.items()}, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run toolgate evaluation suite")
    parser.add_argument(
        "--mode",
        action="append",
        choices=[m.value for m in Mode],
        help="Mode to run (repeatable). Default: all three.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory for JSONL and metrics",
    )
    args = parser.parse_args(argv)
    modes = [Mode(value) for value in args.mode] if args.mode else None
    summary = run_all(modes=modes, out_dir=args.out)
    for name, metrics in summary.items():
        print(
            f"{name}: unauthorized_pass={metrics.unauthorized_pass_rate:.2f} "
            f"false_block={metrics.false_block_rate:.2f} "
            f"completion={metrics.legitimate_completion_rate:.2f}"
        )


if __name__ == "__main__":
    main()
