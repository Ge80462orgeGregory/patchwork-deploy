"""Tests for patchwork.rollback."""
import time
import json
import pytest
from pathlib import Path

from patchwork.core import ServiceConfig
from patchwork.rollback import Snapshot, RollbackStore


def make_config(name: str = "web", image: str = "nginx:1.0", replicas: int = 2) -> ServiceConfig:
    return ServiceConfig(
        name=name,
        image=image,
        replicas=replicas,
        env={"ENV": "prod"},
        host="10.0.0.1",
    )


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "snapshots.json"


class TestSnapshot:
    def test_round_trip(self):
        cfg = make_config()
        snap = Snapshot(service="web", timestamp=1234567890.0, config=cfg)
        restored = Snapshot.from_dict(snap.to_dict())
        assert restored.service == snap.service
        assert restored.timestamp == snap.timestamp
        assert restored.config.image == snap.config.image


class TestRollbackStore:
    def test_save_and_retrieve(self, store_path):
        store = RollbackStore(store_path)
        cfg = make_config()
        store.save(cfg)
        snap = store.latest("web")
        assert snap is not None
        assert snap.config.image == "nginx:1.0"

    def test_latest_returns_none_for_unknown_service(self, store_path):
        store = RollbackStore(store_path)
        assert store.latest("unknown") is None

    def test_save_overwrites_previous_snapshot(self, store_path):
        store = RollbackStore(store_path)
        store.save(make_config(image="nginx:1.0"))
        store.save(make_config(image="nginx:2.0"))
        snap = store.latest("web")
        assert snap.config.image == "nginx:2.0"

    def test_persists_to_disk(self, store_path):
        store = RollbackStore(store_path)
        store.save(make_config())
        # reload from disk
        store2 = RollbackStore(store_path)
        snap = store2.latest("web")
        assert snap is not None
        assert snap.config.name == "web"

    def test_remove_clears_entry(self, store_path):
        store = RollbackStore(store_path)
        store.save(make_config())
        store.remove("web")
        assert store.latest("web") is None

    def test_multiple_services_isolated(self, store_path):
        store = RollbackStore(store_path)
        store.save(make_config(name="web", image="nginx:1.0"))
        store.save(make_config(name="api", image="flask:2.0"))
        assert store.latest("web").config.image == "nginx:1.0"
        assert store.latest("api").config.image == "flask:2.0"

    def test_file_created_in_nested_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "snapshots.json"
        store = RollbackStore(nested)
        store.save(make_config())
        assert nested.exists()
