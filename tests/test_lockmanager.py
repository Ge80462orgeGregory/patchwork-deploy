"""Tests for patchwork.lockmanager."""
import time
import pytest
from pathlib import Path
from patchwork.lockmanager import LockEntry, LockError, LockManager


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "locks.json"


@pytest.fixture
def manager(store_path: Path) -> LockManager:
    return LockManager(store_path)


# ---------------------------------------------------------------------------
# LockEntry unit tests
# ---------------------------------------------------------------------------

class TestLockEntry:
    def test_round_trip(self):
        entry = LockEntry(service="api", owner="ci-bot", ttl_seconds=60.0)
        restored = LockEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.owner == entry.owner
        assert restored.ttl_seconds == entry.ttl_seconds

    def test_not_expired_when_fresh(self):
        entry = LockEntry(service="api", owner="ci", ttl_seconds=300.0)
        assert not entry.is_expired()

    def test_expired_when_old(self):
        entry = LockEntry(
            service="api", owner="ci", acquired_at=time.time() - 400, ttl_seconds=300.0
        )
        assert entry.is_expired()

    def test_repr_contains_key_fields(self):
        entry = LockEntry(service="worker", owner="deploy-agent")
        r = repr(entry)
        assert "worker" in r
        assert "deploy-agent" in r


# ---------------------------------------------------------------------------
# LockManager tests
# ---------------------------------------------------------------------------

class TestLockManager:
    def test_acquire_returns_entry(self, manager):
        entry = manager.acquire("api", "ci-bot")
        assert entry.service == "api"
        assert entry.owner == "ci-bot"

    def test_acquire_same_service_twice_raises(self, manager):
        manager.acquire("api", "ci-bot")
        with pytest.raises(LockError, match="locked by"):
            manager.acquire("api", "other-bot")

    def test_acquire_different_services_ok(self, manager):
        manager.acquire("api", "ci-bot")
        entry2 = manager.acquire("worker", "ci-bot")
        assert entry2.service == "worker"

    def test_release_removes_lock(self, manager):
        manager.acquire("api", "ci-bot")
        released = manager.release("api", "ci-bot")
        assert released is True
        assert "api" not in manager.status()

    def test_release_wrong_owner_raises(self, manager):
        manager.acquire("api", "ci-bot")
        with pytest.raises(LockError, match="owned by"):
            manager.release("api", "intruder")

    def test_release_nonexistent_returns_false(self, manager):
        assert manager.release("ghost", "nobody") is False

    def test_status_excludes_expired(self, manager, store_path):
        entry = LockEntry(
            service="api", owner="ci", acquired_at=time.time() - 500, ttl_seconds=300.0
        )
        manager._locks["api"] = entry
        manager._save()
        assert "api" not in manager.status()

    def test_purge_expired_removes_stale(self, manager):
        manager._locks["stale"] = LockEntry(
            service="stale", owner="x", acquired_at=time.time() - 999, ttl_seconds=10.0
        )
        manager._locks["fresh"] = LockEntry(service="fresh", owner="y", ttl_seconds=300.0)
        purged = manager.purge_expired()
        assert purged == 1
        assert "fresh" in manager._locks
        assert "stale" not in manager._locks

    def test_persists_across_instances(self, store_path):
        m1 = LockManager(store_path)
        m1.acquire("api", "ci-bot")
        m2 = LockManager(store_path)
        assert "api" in m2.status()

    def test_expired_lock_can_be_reacquired(self, manager):
        manager._locks["api"] = LockEntry(
            service="api", owner="old", acquired_at=time.time() - 600, ttl_seconds=300.0
        )
        entry = manager.acquire("api", "new-owner")
        assert entry.owner == "new-owner"
