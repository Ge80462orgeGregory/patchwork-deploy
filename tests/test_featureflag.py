"""Tests for patchwork.featureflag."""
import json
import pytest
from pathlib import Path

from patchwork.featureflag import FeatureFlag, FeatureFlagError, FeatureFlagStore


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "flags.json"


@pytest.fixture
def store(store_path: Path) -> FeatureFlagStore:
    return FeatureFlagStore(store_path)


def _make_flag(name="canary", enabled=True, services=None) -> FeatureFlag:
    return FeatureFlag(name=name, enabled=enabled, services=services or [], description="test flag")


class TestFeatureFlag:
    def test_round_trip(self):
        flag = _make_flag(services=["api", "worker"])
        restored = FeatureFlag.from_dict(flag.to_dict())
        assert restored.name == flag.name
        assert restored.enabled == flag.enabled
        assert restored.services == flag.services
        assert restored.description == flag.description

    def test_applies_to_all_when_empty_services(self):
        flag = _make_flag(services=[])
        assert flag.applies_to("any-service") is True

    def test_applies_to_specific_service(self):
        flag = _make_flag(services=["api"])
        assert flag.applies_to("api") is True
        assert flag.applies_to("worker") is False

    def test_repr_contains_name_and_status(self):
        flag = _make_flag(name="rollout", enabled=False)
        r = repr(flag)
        assert "rollout" in r
        assert "off" in r

    def test_repr_shows_wildcard_scope_for_empty_services(self):
        flag = _make_flag(services=[])
        assert "*" in repr(flag)


class TestFeatureFlagStore:
    def test_initially_empty(self, store: FeatureFlagStore):
        assert len(store) == 0

    def test_set_and_retrieve(self, store: FeatureFlagStore):
        flag = _make_flag()
        store.set(flag)
        assert len(store) == 1
        assert store.is_enabled("canary") is True

    def test_disabled_flag_returns_false(self, store: FeatureFlagStore):
        store.set(_make_flag(enabled=False))
        assert store.is_enabled("canary") is False

    def test_unknown_flag_returns_false(self, store: FeatureFlagStore):
        assert store.is_enabled("nonexistent") is False

    def test_is_enabled_with_matching_service(self, store: FeatureFlagStore):
        store.set(_make_flag(services=["api"]))
        assert store.is_enabled("canary", service="api") is True

    def test_is_enabled_with_non_matching_service(self, store: FeatureFlagStore):
        store.set(_make_flag(services=["api"]))
        assert store.is_enabled("canary", service="worker") is False

    def test_remove_existing_flag(self, store: FeatureFlagStore):
        store.set(_make_flag())
        store.remove("canary")
        assert len(store) == 0

    def test_remove_missing_flag_raises(self, store: FeatureFlagStore):
        with pytest.raises(FeatureFlagError):
            store.remove("ghost")

    def test_persists_to_disk(self, store_path: Path):
        s1 = FeatureFlagStore(store_path)
        s1.set(_make_flag(name="dark-launch", enabled=True))
        s2 = FeatureFlagStore(store_path)
        assert s2.is_enabled("dark-launch") is True

    def test_list_flags_returns_all(self, store: FeatureFlagStore):
        store.set(_make_flag(name="a"))
        store.set(_make_flag(name="b"))
        names = {f.name for f in store.list_flags()}
        assert names == {"a", "b"}
