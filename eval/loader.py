"""Load Case and Oracle JSON files from data/cases."""

from __future__ import annotations

from pathlib import Path

from toolgate.domain.models import Case, Oracle

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = REPO_ROOT / "data" / "cases"
SUITE_DIRS = ("legitimate", "attack")


def case_paths(directory: Path | None = None) -> list[Path]:
    root = directory or CASES_DIR
    paths: list[Path] = []
    for name in SUITE_DIRS:
        folder = root / name
        if folder.is_dir():
            paths.extend(sorted(folder.glob("case_*.json")))
    return [path for path in paths if not path.name.endswith(".oracle.json")]


def load_case(path: Path) -> Case:
    return Case.model_validate_json(path.read_text(encoding="utf-8"))


def load_oracle(path: Path) -> Oracle:
    oracle_path = path.with_name(path.stem + ".oracle.json")
    return Oracle.model_validate_json(oracle_path.read_text(encoding="utf-8"))


def load_suite(directory: Path | None = None) -> list[tuple[Case, Oracle]]:
    return [(load_case(path), load_oracle(path)) for path in case_paths(directory)]


def threat_ids(directory: Path | None = None) -> set[str]:
    return {case.threat_id for case, _ in load_suite(directory) if case.threat_id}
