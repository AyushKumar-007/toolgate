"""SQLite-backed Store. Schema is created on open."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from toolgate.domain.models import Approval, AuditRecord, Principal, Record
from toolgate.domain.vocab import RECORD_FIELDS, Effect, Role, RuleId, ToolName


class SqliteStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        # FastAPI runs sync routes in a worker thread; allow shared connection use.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              user_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              role TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records (
              record_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              owner_id TEXT NOT NULL,
              title TEXT NOT NULL,
              body TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
              token TEXT PRIMARY KEY,
              tool_name TEXT NOT NULL,
              resource_id TEXT,
              user_id TEXT NOT NULL,
              expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audits (
              audit_id TEXT PRIMARY KEY,
              call_id TEXT NOT NULL,
              effect TEXT NOT NULL,
              rule_id TEXT NOT NULL,
              reason TEXT NOT NULL,
              user_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              tool_name TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def upsert_user(self, principal: Principal) -> Principal:
        self._conn.execute(
            """
            INSERT INTO users (user_id, tenant_id, role) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              tenant_id = excluded.tenant_id,
              role = excluded.role
            """,
            (principal.user_id, principal.tenant_id, principal.role.value),
        )
        self._conn.commit()
        return principal

    def put_approval(self, approval: Approval) -> Approval:
        expires = approval.expires_at.isoformat() if approval.expires_at else None
        self._conn.execute(
            """
            INSERT INTO approvals (token, tool_name, resource_id, user_id, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
              tool_name = excluded.tool_name,
              resource_id = excluded.resource_id,
              user_id = excluded.user_id,
              expires_at = excluded.expires_at
            """,
            (
                approval.token,
                approval.tool_name.value,
                approval.resource_id,
                approval.user_id,
                expires,
            ),
        )
        self._conn.commit()
        return approval

    def get_record(self, record_id: str) -> Record | None:
        row = self._conn.execute(
            "SELECT * FROM records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return None if row is None else Record(**dict(row))

    def list_records(self, tenant_id: str) -> list[Record]:
        rows = self._conn.execute(
            "SELECT * FROM records WHERE tenant_id = ? ORDER BY record_id",
            (tenant_id,),
        ).fetchall()
        return [Record(**dict(row)) for row in rows]

    def create_record(self, record: Record) -> Record:
        try:
            self._conn.execute(
                """
                INSERT INTO records (record_id, tenant_id, owner_id, title, body)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.tenant_id,
                    record.owner_id,
                    record.title,
                    record.body,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"record already exists: {record.record_id}") from exc
        self._conn.commit()
        return record

    def update_record(self, record_id: str, fields: dict[str, str]) -> Record | None:
        current = self.get_record(record_id)
        if current is None:
            return None
        unknown = set(fields) - RECORD_FIELDS
        if unknown:
            raise ValueError(f"fields has unknown keys: {', '.join(sorted(unknown))}")
        updated = current.model_copy(update=fields)
        self._conn.execute(
            """
            UPDATE records SET title = ?, body = ? WHERE record_id = ?
            """,
            (updated.title, updated.body, record_id),
        )
        self._conn.commit()
        return updated

    def delete_record(self, record_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM records WHERE record_id = ?", (record_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def search_records(self, tenant_id: str, field: str, value: str) -> list[Record]:
        if field not in RECORD_FIELDS:
            raise ValueError(f"unsupported search field: {field}")
        rows = self._conn.execute(
            f"SELECT * FROM records WHERE tenant_id = ? AND {field} = ? ORDER BY record_id",
            (tenant_id, value),
        ).fetchall()
        return [Record(**dict(row)) for row in rows]

    def export_records(self, tenant_id: str) -> list[Record]:
        return self.list_records(tenant_id)

    def get_user(self, user_id: str) -> Principal | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return Principal(
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            role=Role(row["role"]),
        )

    def set_role(self, user_id: str, role: Role) -> Principal | None:
        current = self.get_user(user_id)
        if current is None:
            return None
        updated = current.model_copy(update={"role": role})
        return self.upsert_user(updated)

    def get_approval(self, token: str) -> Approval | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        expires = row["expires_at"]
        return Approval(
            token=row["token"],
            tool_name=ToolName(row["tool_name"]),
            resource_id=row["resource_id"],
            user_id=row["user_id"],
            expires_at=datetime.fromisoformat(expires) if expires else None,
        )

    def save_audit(self, record: AuditRecord) -> AuditRecord:
        self._conn.execute(
            """
            INSERT INTO audits (
              audit_id, call_id, effect, rule_id, reason,
              user_id, tenant_id, tool_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.audit_id,
                record.call_id,
                record.effect.value,
                record.rule_id.value,
                record.reason,
                record.user_id,
                record.tenant_id,
                record.tool_name.value,
                record.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return record

    def list_audits(self) -> list[AuditRecord]:
        rows = self._conn.execute(
            "SELECT * FROM audits ORDER BY created_at, audit_id"
        ).fetchall()
        return [
            AuditRecord(
                audit_id=row["audit_id"],
                call_id=row["call_id"],
                effect=Effect(row["effect"]),
                rule_id=RuleId(row["rule_id"]),
                reason=row["reason"],
                user_id=row["user_id"],
                tenant_id=row["tenant_id"],
                tool_name=ToolName(row["tool_name"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def dump_json(self) -> str:
        """Debug helper for tests."""
        return json.dumps(
            {
                "users": [u.model_dump(mode="json") for u in self._all_users()],
                "records": [r.model_dump(mode="json") for r in self.list_records("ten_a")]
                + [r.model_dump(mode="json") for r in self.list_records("ten_b")],
            },
            indent=2,
        )

    def _all_users(self) -> list[Principal]:
        rows = self._conn.execute("SELECT * FROM users ORDER BY user_id").fetchall()
        return [
            Principal(
                user_id=row["user_id"],
                tenant_id=row["tenant_id"],
                role=Role(row["role"]),
            )
            for row in rows
        ]
