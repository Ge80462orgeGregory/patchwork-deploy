"""Tests for patchwork.serviceregistry."""
import pathlib
import pytest

from patchwork.serviceregistry import RegistryError, ServiceEntry, ServiceRegistry


@pytest.fixture()
def store_path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "registry.json"


@pytest.fixture()
def registry(store_path: pathlib.Path) -> ServiceRegistry:
    return ServiceRegistry(store_path)


def _make_entry(name: str = "svc-a", owner: str = "team-x", tier: str = "backend", enabled: bool = True) -> ServiceEntry:
    return ServiceEntry(name=name, owner=owner, tier=tier, tags={"env": "prod"}, enabled=enabled)


class TestServiceEntry:
    def test_round_trip(self):
        e = _make_entry()
        assert ServiceEntry.from_dict(e.to_dict()) == e

    def test_repr_contains_key_fields(self):
        e = _make_entry()
        r = repr(e)
        assert "svc-a" in r
        assert "backend" in r
        assert "team-x" in r

    def test_missing_tags_defaults_to_empty(self):
        e = ServiceEntry.from_dict({"name": "x", "owner": "o", "tier": "frontend"})
        assert e.tags == {}

    def test_enabled_defaults_to_true(self):
        e = ServiceEntry.from_dict({"name": "x", "owner": "o", "tier": "data"})
        assert e.enabled is True


class TestServiceRegistry:
    def test_register_and_get(self, registry: ServiceRegistry):
        e = _make_entry()
        registry.register(e)
        assert registry.get("svc-a") == e

    def test_len_reflects_count(self, registry: ServiceRegistry):
        registry.register(_make_entry("a"))
        registry.register(_make_entry("b"))
        assert len(registry) == 2

    def test_list_all_returns_all_entries(self, registry: ServiceRegistry):
        registry.register(_make_entry("a"))
        registry.register(_make_entry("b"))
        names = {e.name for e in registry.list_all()}
        assert names == {"a", "b"}

    def test_deregister_removes_entry(self, registry: ServiceRegistry):
        registry.register(_make_entry())
        registry.deregister("svc-a")
        assert registry.get("svc-a") is None

    def test_deregister_unknown_raises(self, registry: ServiceRegistry):
        with pytest.raises(RegistryError):
            registry.deregister("ghost")

    def test_by_tier_filters_correctly(self, registry: ServiceRegistry):
        registry.register(_make_entry("fe", tier="frontend"))
        registry.register(_make_entry("be", tier="backend"))
        result = registry.by_tier("frontend")
        assert len(result) == 1
        assert result[0].name == "fe"

    def test_by_owner_filters_correctly(self, registry: ServiceRegistry):
        registry.register(_make_entry("a", owner="alice"))
        registry.register(_make_entry("b", owner="bob"))
        result = registry.by_owner("alice")
        assert len(result) == 1 and result[0].name == "a"

    def test_enabled_services_excludes_disabled(self, registry: ServiceRegistry):
        registry.register(_make_entry("on", enabled=True))
        registry.register(_make_entry("off", enabled=False))
        names = {e.name for e in registry.enabled_services()}
        assert "on" in names and "off" not in names

    def test_persistence_across_instances(self, store_path: pathlib.Path):
        r1 = ServiceRegistry(store_path)
        r1.register(_make_entry("persistent"))
        r2 = ServiceRegistry(store_path)
        assert r2.get("persistent") is not None

    def test_get_unknown_returns_none(self, registry: ServiceRegistry):
        assert registry.get("nope") is None
