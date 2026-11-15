from toolgate.domain.protocols import Store
from toolgate.domain.vocab import Role
from toolgate.store import SqliteStore, seed_store


def test_seed_loads_two_tenants() -> None:
    store = SqliteStore(":memory:")
    seed_store(store)
    assert isinstance(store, Store)
    assert store.get_user("usr_ana") is not None
    assert store.get_user("usr_ben") is not None
    assert store.get_user("usr_cara") is not None
    assert store.get_record("rec_a1") is not None
    assert store.get_record("rec_a2") is not None
    assert store.get_record("rec_b1") is not None
    assert len(store.list_records("ten_a")) == 2
    assert len(store.list_records("ten_b")) == 1
    assert store.get_approval("apr_delete_a1") is not None


def test_crud_and_search() -> None:
    store = SqliteStore(":memory:")
    seed_store(store)
    found = store.search_records("ten_a", "title", "Ana note")
    assert len(found) == 1
    updated = store.update_record("rec_a1", {"title": "Renamed"})
    assert updated is not None
    assert updated.title == "Renamed"
    assert store.delete_record("rec_a2") is True
    assert store.get_record("rec_a2") is None
    promoted = store.set_role("usr_ana", Role.admin)
    assert promoted is not None
    assert promoted.role is Role.admin
