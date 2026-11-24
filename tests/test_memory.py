import pytest
from mem0_lite import ConsentRequiredError, MemoryStore, UnsafeMemoryError


def test_consent_required_and_search():
    with MemoryStore(":memory:") as store:
        with pytest.raises(ConsentRequiredError):
            store.remember("u1", "prefers Tamil")
        store.grant_consent("u1")
        memory_id = store.remember("u1", "Prefers answers in Tamil", "preference")
        assert store.search("u1", "Tamil")[0]["id"] == memory_id


def test_revoke_deletes_by_default():
    with MemoryStore(":memory:") as store:
        store.grant_consent("u1")
        store.remember("u1", "likes music")
        store.revoke_consent("u1")
        assert store.search("u1") == []
        with pytest.raises(ConsentRequiredError):
            store.remember("u1", "another memory")


def test_forget_is_user_scoped():
    with MemoryStore(":memory:") as store:
        store.grant_consent("u1")
        store.grant_consent("u2")
        memory_id = store.remember("u1", "likes tea")
        store.remember("u2", "likes coffee")
        assert store.forget("u2", memory_id) is False
        assert store.forget_all("u1") == 1
        assert len(store.search("u2")) == 1


def test_credential_rejected():
    with MemoryStore(":memory:") as store:
        store.grant_consent("u1")
        with pytest.raises(UnsafeMemoryError):
            store.remember("u1", "password: hunter2")
