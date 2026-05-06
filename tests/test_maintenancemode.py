"""Tests for patchwork.maintenancemode."""
import json
import time
import pytest
from pathlib import Path
from patchwork.maintenancemode import (
    MaintenanceEntry,
    MaintenanceError,
    MaintenanceStore,
)


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "maintenance.json"


@pytest.fixture
def store(store_path: Path) -> MaintenanceStore:
    return MaintenanceStore(store_path)


class TestMaintenanceEntry:
    def test_round_trip(self):
        entry = MaintenanceEntry(
            service="api",
            reason="upgrade",
            enabled_at=1_000_000.0,
            enabled_by="alice",
        )
        restored = MaintenanceEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.reason == entry.reason
        assert restored.enabled_by == entry.enabled_by
        assert restored.disabled_at is None

    def test_is_active_when_no_disabled_at(self):
        entry = MaintenanceEntry("svc", "reason", 1.0, "bob")
        assert entry.is_active is True

    def test_not_active_when_disabled_at_set(self):
        entry = MaintenanceEntry("svc", "reason", 1.0, "bob", disabled_at=2.0)
        assert entry.is_active is False

    def test_repr_contains_service_and_status(self):
        entry = MaintenanceEntry("svc", "r", 1.0, "bob")
        r = repr(entry)
        assert "svc" in r
        assert "active" in r


class TestMaintenanceStore:
    def test_enable_creates_active_entry(self, store: MaintenanceStore):
        entry = store.enable("api", "patching", "alice")
        assert entry.is_active
        assert store.is_under_maintenance("api")

    def test_disable_deactivates_entry(self, store: MaintenanceStore):
        store.enable("api", "patching", "alice")
        entry = store.disable("api")
        assert not entry.is_active
        assert not store.is_under_maintenance("api")

    def test_disable_unknown_service_raises(self, store: MaintenanceStore):
        with pytest.raises(MaintenanceError):
            store.disable("nonexistent")

    def test_disable_already_inactive_raises(self, store: MaintenanceStore):
        store.enable("api", "r", "bob")
        store.disable("api")
        with pytest.raises(MaintenanceError):
            store.disable("api")

    def test_active_entries_excludes_disabled(self, store: MaintenanceStore):
        store.enable("api", "r", "alice")
        store.enable("worker", "r", "bob")
        store.disable("api")
        active = store.active_entries()
        assert len(active) == 1
        assert active[0].service == "worker"

    def test_all_entries_includes_inactive(self, store: MaintenanceStore):
        store.enable("api", "r", "alice")
        store.disable("api")
        assert len(store.all_entries()) == 1

    def test_persists_across_instances(self, store_path: Path):
        s1 = MaintenanceStore(store_path)
        s1.enable("db", "migration", "carol")
        s2 = MaintenanceStore(store_path)
        assert s2.is_under_maintenance("db")

    def test_unknown_service_not_under_maintenance(self, store: MaintenanceStore):
        assert not store.is_under_maintenance("ghost")
