from toolgate.domain.models import ToolCall
from toolgate.domain.protocols import ToolRuntime
from toolgate.domain.vocab import Role, ToolName, ToolStatus
from toolgate.store import SqliteStore, seed_store
from toolgate.tools import SimulatedRuntime


def _runtime_and_store() -> tuple[SimulatedRuntime, SqliteStore]:
    store = SqliteStore(":memory:")
    seed_store(store)
    return SimulatedRuntime(), store


def test_all_eight_tools() -> None:
    runtime, store = _runtime_and_store()
    assert isinstance(runtime, ToolRuntime)

    listed = runtime.execute(
        ToolCall(call_id="1", name=ToolName.list_records, arguments={"tenant_id": "ten_a"}),
        store,
    )
    assert listed.status is ToolStatus.ok
    assert len(listed.payload["records"]) == 2

    read = runtime.execute(
        ToolCall(call_id="2", name=ToolName.read_record, arguments={"record_id": "rec_a1"}),
        store,
    )
    assert read.status is ToolStatus.ok

    search = runtime.execute(
        ToolCall(
            call_id="3",
            name=ToolName.search_records,
            arguments={"tenant_id": "ten_a", "field": "title", "value": "Ana note"},
        ),
        store,
    )
    assert search.status is ToolStatus.ok
    assert len(search.payload["records"]) == 1

    created = runtime.execute(
        ToolCall(
            call_id="4",
            name=ToolName.create_record,
            arguments={
                "tenant_id": "ten_b",
                "owner_id": "usr_ben",
                "title": "New",
                "body": "Body",
            },
        ),
        store,
    )
    assert created.status is ToolStatus.ok

    updated = runtime.execute(
        ToolCall(
            call_id="5",
            name=ToolName.update_record,
            arguments={"record_id": "rec_b1", "fields": {"title": "Updated"}},
        ),
        store,
    )
    assert updated.status is ToolStatus.ok
    assert updated.payload["record"]["title"] == "Updated"

    exported = runtime.execute(
        ToolCall(
            call_id="6",
            name=ToolName.export_records,
            arguments={"tenant_id": "ten_a", "approval_token": "apr_export_a"},
        ),
        store,
    )
    assert exported.status is ToolStatus.ok

    perms = runtime.execute(
        ToolCall(
            call_id="7",
            name=ToolName.change_permissions,
            arguments={
                "user_id": "usr_ana",
                "role": Role.editor.value,
                "approval_token": "apr_perm_ben",
            },
        ),
        store,
    )
    assert perms.status is ToolStatus.ok
    assert store.get_user("usr_ana").role is Role.editor

    deleted = runtime.execute(
        ToolCall(
            call_id="8",
            name=ToolName.delete_record,
            arguments={"record_id": "rec_a2", "approval_token": "apr_delete_a1"},
        ),
        store,
    )
    assert deleted.status is ToolStatus.ok
    assert store.get_record("rec_a2") is None


def test_tools_do_not_enforce_policy() -> None:
    """Direct baseline must be able to perform an unauthorized action."""
    runtime, store = _runtime_and_store()
    result = runtime.execute(
        ToolCall(call_id="x", name=ToolName.read_record, arguments={"record_id": "rec_b1"}),
        store,
    )
    assert result.status is ToolStatus.ok
