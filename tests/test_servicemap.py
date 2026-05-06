"""Tests for patchwork.servicemap."""
import json
import pathlib
import pytest

from patchwork.servicemap import ServiceEntry, ServiceMap, ServiceMapError


def _make_entry(service="api", host="10.0.0.1", environment="prod", tags=None) -> ServiceEntry:
    return ServiceEntry(service=service, host=host, environment=environment, tags=tags or {})


# ---------------------------------------------------------------------------
# ServiceEntry
# ---------------------------------------------------------------------------

class TestServiceEntry:
    def test_round_trip(self):
        e = _make_entry(tags={"region": "us-east"})
        assert ServiceEntry.from_dict(e.to_dict()) == e

    def test_repr_contains_key_fields(self):
        e = _make_entry()
        r = repr(e)
        assert "api" in r
        assert "10.0.0.1" in r
        assert "prod" in r

    def test_missing_tags_defaults_to_empty(self):
        data = {"service": "api", "host": "h", "environment": "dev"}
        e = ServiceEntry.from_dict(data)
        assert e.tags == {}


# ---------------------------------------------------------------------------
# ServiceMap
# ---------------------------------------------------------------------------

class TestServiceMap:
    def test_register_and_len(self):
        sm = ServiceMap()
        sm.register(_make_entry())
        assert len(sm) == 1

    def test_duplicate_upserts_entry(self):
        sm = ServiceMap()
        sm.register(_make_entry(environment="staging"))
        sm.register(_make_entry(environment="prod"))
        assert len(sm) == 1
        assert sm.lookup("api", "10.0.0.1").environment == "prod"

    def test_by_service(self):
        sm = ServiceMap()
        sm.register(_make_entry(service="api", host="h1"))
        sm.register(_make_entry(service="api", host="h2"))
        sm.register(_make_entry(service="worker", host="h3"))
        assert len(sm.by_service("api")) == 2

    def test_by_host(self):
        sm = ServiceMap()
        sm.register(_make_entry(service="api", host="h1"))
        sm.register(_make_entry(service="worker", host="h1"))
        sm.register(_make_entry(service="api", host="h2"))
        assert len(sm.by_host("h1")) == 2

    def test_by_environment(self):
        sm = ServiceMap()
        sm.register(_make_entry(environment="prod"))
        sm.register(_make_entry(service="worker", host="h2", environment="staging"))
        assert len(sm.by_environment("prod")) == 1

    def test_lookup_returns_none_when_missing(self):
        sm = ServiceMap()
        assert sm.lookup("ghost", "nowhere") is None

    def test_remove_returns_true_on_success(self):
        sm = ServiceMap()
        sm.register(_make_entry())
        assert sm.remove("api", "10.0.0.1") is True
        assert len(sm) == 0

    def test_remove_returns_false_when_not_found(self):
        sm = ServiceMap()
        assert sm.remove("ghost", "nowhere") is False


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestServiceMapPersistence:
    def test_save_and_load_round_trip(self, tmp_path):
        p = tmp_path / "map.json"
        sm = ServiceMap()
        sm.register(_make_entry(tags={"az": "a"}))
        sm.save(p)
        loaded = ServiceMap.load(p)
        assert len(loaded) == 1
        assert loaded.lookup("api", "10.0.0.1").tags == {"az": "a"}

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(ServiceMapError, match="not found"):
            ServiceMap.load(tmp_path / "missing.json")

    def test_load_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not-json")
        with pytest.raises(ServiceMapError, match="Invalid JSON"):
            ServiceMap.load(p)
