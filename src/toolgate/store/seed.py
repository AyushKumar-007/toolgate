"""Load synthetic seed data into a Store."""

from __future__ import annotations

import json
from pathlib import Path

from toolgate.domain.models import Approval, Principal, Record
from toolgate.domain.protocols import Store
from toolgate.domain.vocab import Role, ToolName

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED = REPO_ROOT / "data" / "synthetic" / "seed.json"


def default_seed_path() -> Path:
    return DEFAULT_SEED


def load_seed(path: Path | None = None) -> dict:
    target = path or DEFAULT_SEED
    return json.loads(target.read_text(encoding="utf-8"))


def seed_store(store: Store, path: Path | None = None) -> None:
    payload = load_seed(path)
    upsert = getattr(store, "upsert_user", None)
    put_approval = getattr(store, "put_approval", None)
    if upsert is None or put_approval is None:
        raise TypeError("store must support upsert_user and put_approval for seeding")

    for user in payload["users"]:
        upsert(
            Principal(
                user_id=user["user_id"],
                tenant_id=user["tenant_id"],
                role=Role(user["role"]),
            )
        )
    for row in payload["records"]:
        store.create_record(Record.model_validate(row))
    for row in payload["approvals"]:
        put_approval(
            Approval(
                token=row["token"],
                tool_name=ToolName(row["tool_name"]),
                resource_id=row.get("resource_id"),
                user_id=row["user_id"],
                expires_at=row.get("expires_at"),
            )
        )
