"""Tests for patchwork.tagstore."""
import json
import pytest
from pathlib import Path

from patchwork.tagstore import DeploymentTag, TagStore, TagError


@pytest.fixture
def store_path(tmp_path) -> Path:
    return tmp_path / "tags.json"


@pytest.fixture
def store(store_path) -> TagStore:
    return TagStore(path=store_path)


def _make_tag(service="svc-a", deploy_id="d001", **tags) -> DeploymentTag:
    return DeploymentTag(service=service, deploy_id=deploy_id, tags=tags or {"env": "prod"})


class TestDeploymentTag:
    def test_round_trip(self):
        tag = _make_tag(env="staging", version="1.2.3")
        restored = DeploymentTag.from_dict(tag.to_dict())
        assert restored.service == tag.service
        assert restored.deploy_id == tag.deploy_id
        assert restored.tags == tag.tags
        assert restored.created_at == tag.created_at

    def test_repr_contains_key_fields(self):
        tag = _make_tag()
        r = repr(tag)
        assert "svc-a" in r
        assert "d001" in r


class TestTagStorePut:
    def test_put_creates_file(self, store, store_path):
        store.put(_make_tag())
        assert store_path.exists()

    def test_put_multiple_records(self, store):
        store.put(_make_tag(deploy_id="d001"))
        store.put(_make_tag(deploy_id="d002"))
        assert len(store.list_for_service("svc-a")) == 2


class TestTagStoreGet:
    def test_get_existing(self, store):
        store.put(_make_tag(env="prod"))
        result = store.get("svc-a", "d001")
        assert result is not None
        assert result.tags["env"] == "prod"

    def test_get_missing_returns_none(self, store):
        assert store.get("svc-a", "missing") is None

    def test_get_wrong_service_returns_none(self, store):
        store.put(_make_tag(service="svc-b"))
        assert store.get("svc-a", "d001") is None


class TestTagStoreList:
    def test_list_filters_by_service(self, store):
        store.put(_make_tag(service="svc-a", deploy_id="d1"))
        store.put(_make_tag(service="svc-b", deploy_id="d2"))
        results = store.list_for_service("svc-a")
        assert len(results) == 1
        assert results[0].service == "svc-a"

    def test_list_empty_when_no_records(self, store):
        assert store.list_for_service("svc-x") == []


class TestTagStoreFind:
    def test_find_by_tag_matches(self, store):
        store.put(_make_tag(deploy_id="d1", env="prod"))
        store.put(_make_tag(deploy_id="d2", env="staging"))
        results = store.find_by_tag("env", "prod")
        assert len(results) == 1
        assert results[0].deploy_id == "d1"

    def test_find_by_tag_no_match(self, store):
        store.put(_make_tag(env="prod"))
        assert store.find_by_tag("env", "canary") == []


class TestTagStoreDelete:
    def test_delete_existing_returns_true(self, store):
        store.put(_make_tag())
        assert store.delete("svc-a", "d001") is True
        assert store.get("svc-a", "d001") is None

    def test_delete_missing_returns_false(self, store):
        assert store.delete("svc-a", "ghost") is False

    def test_delete_leaves_others_intact(self, store):
        store.put(_make_tag(deploy_id="d1"))
        store.put(_make_tag(deploy_id="d2"))
        store.delete("svc-a", "d1")
        assert store.get("svc-a", "d2") is not None
