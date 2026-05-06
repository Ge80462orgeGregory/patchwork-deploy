"""Tests for patchwork.dependencylock."""
from __future__ import annotations

import time
import pytest
from pathlib import Path

from patchwork.dependencylock import (
    DependencyLockEntry,
    DependencyLockError,
    DependencyLockManager,
)


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "dep_locks.json"


@pytest.fixture
def manager(store_path: Path) -> DependencyLockManager:
    return DependencyLockManager(store_path)


class TestDependencyLockEntry:
    def test_round_trip(self):
        entry = DependencyLockEntry(service="api", locked_by="pipeline-1", ttl_seconds=60)
        restored = DependencyLockEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.locked_by == entry.locked_by
        assert restored.ttl_seconds == entry.ttl_seconds

    def test_not_expired_when_fresh(self):
        entry = DependencyLockEntry(service="api", locked_by="x", ttl_seconds=300)
        assert not entry.is_expired()

    def test_expired_when_old(self):
        entry = DependencyLockEntry(
            service="api", locked_by="x", locked_at=time.time() - 400, ttl_seconds=300
        )
        assert entry.is_expired()

    def test_repr_contains_service(self):
        entry = DependencyLockEntry(service="worker", locked_by="ci")
        assert "worker" in repr(entry)
        assert "ci" in repr(entry)


class TestDependencyLockManager:
    def test_acquire_creates_lock(self, manager: DependencyLockManager):
        entry = manager.acquire("api", locked_by="deploy-1")
        assert entry.service == "api"
        assert entry.locked_by == "deploy-1"

    def test_acquire_duplicate_raises(self, manager: DependencyLockManager):
        manager.acquire("api", locked_by="deploy-1")
        with pytest.raises(DependencyLockError, match="already locked"):
            manager.acquire("api", locked_by="deploy-2")

    def test_release_removes_lock(self, manager: DependencyLockManager):
        manager.acquire("api", locked_by="deploy-1")
        removed = manager.release("api")
        assert removed is True
        assert manager.all_locks() == []

    def test_release_nonexistent_returns_false(self, manager: DependencyLockManager):
        assert manager.release("ghost") is False

    def test_check_dependencies_returns_blocked(self, manager: DependencyLockManager):
        manager.acquire("db", locked_by="pipeline-A")
        blocked = manager.check_dependencies(["db", "cache"])
        assert blocked == ["db"]

    def test_check_dependencies_empty_when_none_locked(self, manager: DependencyLockManager):
        blocked = manager.check_dependencies(["db", "cache"])
        assert blocked == []

    def test_expired_locks_are_pruned_on_acquire(self, store_path: Path):
        mgr = DependencyLockManager(store_path)
        # Manually insert an expired lock
        expired = DependencyLockEntry(
            service="old", locked_by="stale", locked_at=time.time() - 999, ttl_seconds=10
        )
        mgr._locks["old"] = expired
        mgr._save()
        # Reload and acquire same service — should succeed after prune
        mgr2 = DependencyLockManager(store_path)
        entry = mgr2.acquire("old", locked_by="fresh")
        assert entry.locked_by == "fresh"

    def test_persists_across_instances(self, store_path: Path):
        m1 = DependencyLockManager(store_path)
        m1.acquire("svc", locked_by="run-1")
        m2 = DependencyLockManager(store_path)
        locks = m2.all_locks()
        assert any(l.service == "svc" for l in locks)
