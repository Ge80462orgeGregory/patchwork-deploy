"""Tests for patchwork.quotamanager."""
import json
import time
import pytest
from pathlib import Path
from patchwork.quotamanager import QuotaEntry, QuotaExceeded, QuotaManager


# ---------------------------------------------------------------------------
# QuotaEntry unit tests
# ---------------------------------------------------------------------------

class TestQuotaEntry:
    def _entry(self, max_deploys=3, window=60):
        return QuotaEntry(service="svc", max_deploys=max_deploys, window_seconds=window)

    def test_initially_allowed(self):
        assert self._entry().is_allowed() is True

    def test_remaining_starts_at_max(self):
        e = self._entry(max_deploys=5)
        assert e.remaining() == 5

    def test_record_decrements_remaining(self):
        e = self._entry(max_deploys=3)
        now = time.time()
        e.record(now)
        assert e.remaining(now) == 2

    def test_not_allowed_when_quota_full(self):
        e = self._entry(max_deploys=2)
        now = time.time()
        e.record(now)
        e.record(now)
        assert e.is_allowed(now) is False

    def test_old_entries_pruned_outside_window(self):
        e = self._entry(max_deploys=2, window=10)
        old = time.time() - 20
        e.deploy_times = [old, old]  # two stale entries
        now = time.time()
        assert e.is_allowed(now) is True
        assert e.remaining(now) == 2

    def test_round_trip(self):
        e = QuotaEntry("api", 5, 3600, [1_000_000.0])
        restored = QuotaEntry.from_dict(e.to_dict())
        assert restored.service == e.service
        assert restored.max_deploys == e.max_deploys
        assert restored.window_seconds == e.window_seconds
        assert restored.deploy_times == e.deploy_times


# ---------------------------------------------------------------------------
# QuotaManager integration tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "quota.json"


@pytest.fixture()
def manager(store_path: Path) -> QuotaManager:
    return QuotaManager(store_path)


class TestQuotaManager:
    def test_configure_creates_entry(self, manager):
        e = manager.configure("web", max_deploys=3, window_seconds=60)
        assert e.service == "web"
        assert e.max_deploys == 3

    def test_configure_persists_to_disk(self, store_path, manager):
        manager.configure("web", 3, 60)
        raw = json.loads(store_path.read_text())
        assert any(r["service"] == "web" for r in raw)

    def test_check_and_record_succeeds_within_limit(self, manager):
        manager.configure("api", 2, 60)
        now = time.time()
        manager.check_and_record("api", now)
        entry = manager._entries["api"]
        assert len(entry.deploy_times) == 1

    def test_check_and_record_raises_when_exceeded(self, manager):
        manager.configure("api", 1, 60)
        now = time.time()
        manager.check_and_record("api", now)
        with pytest.raises(QuotaExceeded):
            manager.check_and_record("api", now)

    def test_unknown_service_raises_key_error(self, manager):
        with pytest.raises(KeyError):
            manager.check_and_record("ghost")

    def test_status_returns_all_services(self, manager):
        manager.configure("a", 5, 60)
        manager.configure("b", 2, 30)
        s = manager.status()
        assert "a" in s and "b" in s

    def test_reload_preserves_deploy_times(self, store_path, manager):
        manager.configure("svc", 5, 3600)
        now = time.time()
        manager.check_and_record("svc", now)
        reloaded = QuotaManager(store_path)
        assert len(reloaded._entries["svc"].deploy_times) == 1

    def test_configure_preserves_existing_times(self, manager):
        manager.configure("svc", 5, 3600)
        now = time.time()
        manager.check_and_record("svc", now)
        # reconfigure without wiping history
        manager.configure("svc", 10, 3600)
        assert len(manager._entries["svc"].deploy_times) == 1
