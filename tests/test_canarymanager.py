"""Tests for patchwork.canarymanager."""
import pytest
from pathlib import Path
from patchwork.canarymanager import CanaryEntry, CanaryError, CanaryManager


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "canary.json"


@pytest.fixture
def manager(store_path: Path) -> CanaryManager:
    return CanaryManager(store_path=store_path)


class TestCanaryEntry:
    def test_valid_weights_sum_to_100(self):
        e = CanaryEntry(service="svc", baseline_weight=80, canary_weight=20)
        assert e.baseline_weight + e.canary_weight == 100

    def test_invalid_weights_raise(self):
        with pytest.raises(CanaryError, match="sum to 100"):
            CanaryEntry(service="svc", baseline_weight=80, canary_weight=30)

    def test_out_of_range_canary_raises(self):
        with pytest.raises(CanaryError, match="canary_weight"):
            CanaryEntry(service="svc", baseline_weight=50, canary_weight=150)

    def test_is_active_initially(self):
        e = CanaryEntry(service="svc", baseline_weight=90, canary_weight=10)
        assert e.is_active() is True

    def test_not_active_after_promote(self):
        e = CanaryEntry(service="svc", baseline_weight=90, canary_weight=10, promoted=True)
        assert e.is_active() is False

    def test_not_active_after_abort(self):
        e = CanaryEntry(service="svc", baseline_weight=90, canary_weight=10, aborted=True)
        assert e.is_active() is False

    def test_round_trip(self):
        e = CanaryEntry(service="svc", baseline_weight=70, canary_weight=30)
        assert CanaryEntry.from_dict(e.to_dict()).canary_weight == 30

    def test_repr_contains_service_and_weight(self):
        e = CanaryEntry(service="api", baseline_weight=80, canary_weight=20)
        r = repr(e)
        assert "api" in r
        assert "20%" in r
        assert "active" in r


class TestCanaryManager:
    def test_create_returns_entry(self, manager: CanaryManager):
        e = manager.create("api", 10)
        assert e.service == "api"
        assert e.canary_weight == 10
        assert e.baseline_weight == 90

    def test_create_persists(self, store_path: Path):
        m = CanaryManager(store_path=store_path)
        m.create("api", 20)
        m2 = CanaryManager(store_path=store_path)
        assert m2.get("api") is not None
        assert m2.get("api").canary_weight == 20

    def test_duplicate_active_raises(self, manager: CanaryManager):
        manager.create("api", 10)
        with pytest.raises(CanaryError, match="already exists"):
            manager.create("api", 20)

    def test_promote(self, manager: CanaryManager):
        manager.create("api", 15)
        e = manager.promote("api")
        assert e.promoted is True
        assert e.is_active() is False

    def test_abort(self, manager: CanaryManager):
        manager.create("api", 15)
        e = manager.abort("api")
        assert e.aborted is True
        assert e.is_active() is False

    def test_promote_unknown_service_raises(self, manager: CanaryManager):
        with pytest.raises(CanaryError, match="No canary entry"):
            manager.promote("ghost")

    def test_promote_already_promoted_raises(self, manager: CanaryManager):
        manager.create("api", 10)
        manager.promote("api")
        with pytest.raises(CanaryError, match="not active"):
            manager.promote("api")

    def test_list_active_returns_only_active(self, manager: CanaryManager):
        manager.create("api", 10)
        manager.create("worker", 20)
        manager.promote("worker")
        active = manager.list_active()
        assert len(active) == 1
        assert active[0].service == "api"

    def test_can_recreate_after_abort(self, manager: CanaryManager):
        manager.create("api", 10)
        manager.abort("api")
        e = manager.create("api", 25)
        assert e.canary_weight == 25
