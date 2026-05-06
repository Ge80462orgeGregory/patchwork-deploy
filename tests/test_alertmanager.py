"""Tests for patchwork.alertmanager."""
import time
from pathlib import Path

import pytest

from patchwork.alertmanager import Alert, AlertManager, Severity


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "alerts.json"


@pytest.fixture
def manager(store_path: Path) -> AlertManager:
    return AlertManager(store_path)


# ---------------------------------------------------------------------------
# Alert dataclass
# ---------------------------------------------------------------------------

class TestAlert:
    def test_not_resolved_initially(self):
        a = Alert(service="svc", message="down", severity=Severity.CRITICAL)
        assert not a.is_resolved

    def test_resolve_sets_timestamp(self):
        a = Alert(service="svc", message="down", severity=Severity.CRITICAL)
        before = time.time()
        a.resolve()
        assert a.resolved_at is not None
        assert a.resolved_at >= before

    def test_round_trip(self):
        a = Alert(service="api", message="latency", severity=Severity.WARNING)
        restored = Alert.from_dict(a.to_dict())
        assert restored.service == a.service
        assert restored.message == a.message
        assert restored.severity == a.severity
        assert restored.fired_at == a.fired_at

    def test_repr_contains_key_fields(self):
        a = Alert(service="db", message="oom", severity=Severity.CRITICAL)
        r = repr(a)
        assert "db" in r
        assert "critical" in r
        assert "firing" in r

    def test_repr_shows_resolved(self):
        a = Alert(service="db", message="oom", severity=Severity.CRITICAL)
        a.resolve()
        assert "resolved" in repr(a)


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------

class TestAlertManager:
    def test_fire_creates_alert(self, manager: AlertManager):
        alert = manager.fire("web", "high cpu", Severity.WARNING)
        assert alert.service == "web"
        assert not alert.is_resolved

    def test_active_for_returns_only_unresolved(self, manager: AlertManager):
        manager.fire("web", "high cpu", Severity.WARNING)
        manager.fire("web", "disk full", Severity.CRITICAL)
        manager.resolve("web", "high cpu")
        active = manager.active_for("web")
        assert len(active) == 1
        assert active[0].message == "disk full"

    def test_resolve_returns_count(self, manager: AlertManager):
        manager.fire("db", "slow query", Severity.INFO)
        manager.fire("db", "slow query", Severity.INFO)
        count = manager.resolve("db", "slow query")
        assert count == 2

    def test_resolve_nonexistent_returns_zero(self, manager: AlertManager):
        assert manager.resolve("ghost", "nope") == 0

    def test_all_active_across_services(self, manager: AlertManager):
        manager.fire("a", "err", Severity.CRITICAL)
        manager.fire("b", "err", Severity.WARNING)
        manager.resolve("a", "err")
        assert len(manager.all_active()) == 1

    def test_summary_counts_by_severity(self, manager: AlertManager):
        manager.fire("x", "m1", Severity.CRITICAL)
        manager.fire("x", "m2", Severity.CRITICAL)
        manager.fire("y", "m3", Severity.WARNING)
        s = manager.summary()
        assert s["critical"] == 2
        assert s["warning"] == 1
        assert s["info"] == 0

    def test_persistence_across_instances(self, store_path: Path):
        m1 = AlertManager(store_path)
        m1.fire("svc", "boom", Severity.CRITICAL)
        m2 = AlertManager(store_path)
        assert len(m2.all_active()) == 1

    def test_history_filters_by_service(self, manager: AlertManager):
        manager.fire("a", "x", Severity.INFO)
        manager.fire("b", "y", Severity.INFO)
        assert len(manager.history("a")) == 1
        assert len(manager.history()) == 2
