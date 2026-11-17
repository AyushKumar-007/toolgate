"""Score legal calls that sit next to the attacks. Separate from the 14-case suite."""

from __future__ import annotations

import json
from pathlib import Path

from eval.loader import load_folder
from eval.score import score
from toolgate.domain.vocab import Mode
from toolgate.enforcement.mode import ModeEnforcement
from toolgate.store.seed import seed_store
from toolgate.store.sqlite import SqliteStore

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "data" / "results" / "borderline_summary.json"


def run_borderline() -> dict:
    suite = load_folder("borderline")
    outcomes = []
    cases = []
    oracles = []
    audited: set[str] = set()
    for case, oracle in suite:
        store = SqliteStore(":memory:")
        seed_store(store)
        outcome = ModeEnforcement(Mode.gateway, store).run(case)
        outcomes.append(outcome)
        cases.append(case)
        oracles.append(oracle)
        audited.update(decision.call_id for decision in outcome.decisions)
    metrics = score(outcomes, cases, oracles, audited_call_ids=audited)
    payload = metrics.to_dict()
    # score() reports coverage of the attack-suite threats. These cases are
    # legitimate near-misses, so that field would read as 0 for the wrong reason.
    payload.pop("threat_coverage", None)
    payload["case_ids"] = [case.case_id for case in cases]
    payload["note"] = (
        "Legitimate near-misses only. Not part of the 14-case suite, "
        "and not a measurement of attack coverage."
    )
    return payload


def main() -> None:
    payload = run_borderline()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
