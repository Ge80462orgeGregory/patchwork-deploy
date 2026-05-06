"""Tests for patchwork.envprofile."""
import json
import pytest

from patchwork.envprofile import EnvProfile, ProfileStore, ProfileError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store_path(tmp_path):
    return str(tmp_path / "profiles.json")


@pytest.fixture
def store(store_path):
    return ProfileStore(store_path)


def _make_profile(name="staging", **kwargs) -> EnvProfile:
    return EnvProfile(name=name, **kwargs)


# ---------------------------------------------------------------------------
# EnvProfile unit tests
# ---------------------------------------------------------------------------

class TestEnvProfile:
    def test_defaults(self):
        p = EnvProfile(name="dev")
        assert p.ssh_user == "deploy"
        assert p.ssh_port == 22
        assert p.env_vars == {}
        assert p.allowed_services == []
        assert p.dry_run is False

    def test_round_trip(self):
        p = EnvProfile(
            name="prod",
            ssh_user="ci",
            ssh_port=2222,
            env_vars={"LOG_LEVEL": "warn"},
            allowed_services=["api", "worker"],
            dry_run=False,
        )
        restored = EnvProfile.from_dict(p.to_dict())
        assert restored.name == p.name
        assert restored.ssh_user == p.ssh_user
        assert restored.ssh_port == p.ssh_port
        assert restored.env_vars == p.env_vars
        assert restored.allowed_services == p.allowed_services

    def test_service_allowed_empty_list_means_all(self):
        p = EnvProfile(name="dev")
        assert p.is_service_allowed("anything") is True

    def test_service_allowed_restricts_correctly(self):
        p = EnvProfile(name="prod", allowed_services=["api"])
        assert p.is_service_allowed("api") is True
        assert p.is_service_allowed("worker") is False

    def test_repr_contains_name(self):
        p = EnvProfile(name="staging")
        assert "staging" in repr(p)

    def test_profile_error_repr(self):
        err = ProfileError("oops")
        assert "oops" in repr(err)


# ---------------------------------------------------------------------------
# ProfileStore tests
# ---------------------------------------------------------------------------

class TestProfileStore:
    def test_initially_empty(self, store):
        assert len(store) == 0
        assert store.list() == []

    def test_save_and_get(self, store):
        p = _make_profile(name="dev")
        store.save(p)
        result = store.get("dev")
        assert result is not None
        assert result.name == "dev"

    def test_get_missing_returns_none(self, store):
        assert store.get("ghost") is None

    def test_save_persists_to_disk(self, store_path):
        s = ProfileStore(store_path)
        s.save(_make_profile(name="ci", ssh_user="runner"))
        # re-open
        s2 = ProfileStore(store_path)
        p = s2.get("ci")
        assert p is not None
        assert p.ssh_user == "runner"

    def test_list_returns_all(self, store):
        store.save(_make_profile("a"))
        store.save(_make_profile("b"))
        names = {p.name for p in store.list()}
        assert names == {"a", "b"}

    def test_delete_removes_profile(self, store):
        store.save(_make_profile("tmp"))
        removed = store.delete("tmp")
        assert removed is True
        assert store.get("tmp") is None

    def test_delete_missing_returns_false(self, store):
        assert store.delete("nope") is False

    def test_overwrite_profile(self, store):
        store.save(_make_profile("dev", dry_run=False))
        store.save(_make_profile("dev", dry_run=True))
        assert store.get("dev").dry_run is True
        assert len(store) == 1
