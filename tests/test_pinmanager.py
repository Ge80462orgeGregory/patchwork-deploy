"""Tests for patchwork.pinmanager."""
import json
import pytest
from pathlib import Path

from patchwork.pinmanager import PinEntry, PinError, PinManager


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "pins.json"


@pytest.fixture
def manager(store_path: Path) -> PinManager:
    return PinManager(store_path=store_path)


class TestPinEntry:
    def test_round_trip(self):
        entry = PinEntry(service="api", pinned_image="api:1.2.3", reason="hotfix", pinned_by="alice", pinned_at=1000.0)
        restored = PinEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.pinned_image == entry.pinned_image
        assert restored.pinned_by == entry.pinned_by
        assert restored.pinned_at == entry.pinned_at

    def test_repr_contains_key_fields(self):
        entry = PinEntry(service="worker", pinned_image="worker:2.0", reason="stability", pinned_by="bob")
        r = repr(entry)
        assert "worker" in r
        assert "worker:2.0" in r
        assert "bob" in r


class TestPinManager:
    def test_initially_empty(self, manager: PinManager):
        assert len(manager) == 0
        assert manager.all_pins() == []

    def test_pin_service(self, manager: PinManager):
        entry = manager.pin("api", "api:1.0", "freeze for release", "alice")
        assert entry.service == "api"
        assert manager.is_pinned("api")
        assert len(manager) == 1

    def test_get_returns_entry(self, manager: PinManager):
        manager.pin("api", "api:1.0", "reason", "alice")
        entry = manager.get("api")
        assert entry is not None
        assert entry.pinned_image == "api:1.0"

    def test_get_unknown_returns_none(self, manager: PinManager):
        assert manager.get("nonexistent") is None

    def test_unpin_removes_entry(self, manager: PinManager):
        manager.pin("api", "api:1.0", "reason", "alice")
        manager.unpin("api")
        assert not manager.is_pinned("api")
        assert len(manager) == 0

    def test_unpin_unknown_raises(self, manager: PinManager):
        with pytest.raises(PinError):
            manager.unpin("ghost")

    def test_pin_overwrites_existing(self, manager: PinManager):
        manager.pin("api", "api:1.0", "first", "alice")
        manager.pin("api", "api:2.0", "second", "bob")
        assert manager.get("api").pinned_image == "api:2.0"
        assert len(manager) == 1

    def test_persists_to_disk(self, store_path: Path):
        m1 = PinManager(store_path=store_path)
        m1.pin("svc", "svc:3.1", "pin it", "carol")
        m2 = PinManager(store_path=store_path)
        assert m2.is_pinned("svc")
        assert m2.get("svc").pinned_image == "svc:3.1"

    def test_all_pins_returns_all(self, manager: PinManager):
        manager.pin("a", "a:1", "r", "u")
        manager.pin("b", "b:2", "r", "u")
        services = {p.service for p in manager.all_pins()}
        assert services == {"a", "b"}

    def test_store_file_is_valid_json(self, manager: PinManager, store_path: Path):
        manager.pin("x", "x:0.1", "test", "tester")
        data = json.loads(store_path.read_text())
        assert "pins" in data
        assert isinstance(data["pins"], list)
