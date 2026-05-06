"""Tests for patchwork.snapshotdiff."""
import pytest

from patchwork.core import ServiceConfig
from patchwork.rollback import Snapshot
from patchwork.snapshotdiff import FieldDelta, SnapshotDiffResult, diff_snapshots


def _make_config(**kwargs) -> ServiceConfig:
    defaults = dict(
        name="svc",
        image="nginx:1.0",
        replicas=1,
        env={},
        ports=[],
        command=None,
    )
    defaults.update(kwargs)
    return ServiceConfig(**defaults)


def _snap(config: ServiceConfig, version: str = "v1") -> Snapshot:
    return Snapshot(service=config.name, version=version, config=config)


# ---------------------------------------------------------------------------
# FieldDelta
# ---------------------------------------------------------------------------

class TestFieldDelta:
    def test_to_dict_contains_all_keys(self):
        d = FieldDelta(field="image", before="a:1", after="a:2")
        result = d.to_dict()
        assert result == {"field": "image", "before": "a:1", "after": "a:2"}


# ---------------------------------------------------------------------------
# SnapshotDiffResult
# ---------------------------------------------------------------------------

class TestSnapshotDiffResult:
    def test_has_changes_false_when_empty(self):
        r = SnapshotDiffResult(service="svc")
        assert r.has_changes is False

    def test_has_changes_true_when_deltas_present(self):
        r = SnapshotDiffResult(
            service="svc",
            deltas=[FieldDelta("image", "a:1", "a:2")],
        )
        assert r.has_changes is True

    def test_summary_no_changes(self):
        r = SnapshotDiffResult(service="svc")
        assert "no changes" in r.summary()

    def test_summary_with_changes(self):
        r = SnapshotDiffResult(
            service="svc",
            deltas=[FieldDelta("replicas", 1, 3)],
        )
        text = r.summary()
        assert "1 change" in text
        assert "replicas" in text

    def test_to_dict_structure(self):
        r = SnapshotDiffResult(
            service="svc",
            deltas=[FieldDelta("image", "a:1", "a:2")],
        )
        d = r.to_dict()
        assert d["service"] == "svc"
        assert d["has_changes"] is True
        assert len(d["deltas"]) == 1


# ---------------------------------------------------------------------------
# diff_snapshots
# ---------------------------------------------------------------------------

class TestDiffSnapshots:
    def test_identical_configs_no_deltas(self):
        cfg = _make_config()
        result = diff_snapshots(_snap(cfg, "v1"), _snap(cfg, "v2"))
        assert not result.has_changes

    def test_image_change_detected(self):
        before = _snap(_make_config(image="nginx:1.0"))
        after = _snap(_make_config(image="nginx:2.0"), version="v2")
        result = diff_snapshots(before, after)
        assert result.has_changes
        assert any(d.field == "image" for d in result.deltas)

    def test_replica_change_detected(self):
        before = _snap(_make_config(replicas=1))
        after = _snap(_make_config(replicas=5), version="v2")
        result = diff_snapshots(before, after)
        fields = [d.field for d in result.deltas]
        assert "replicas" in fields

    def test_env_change_detected(self):
        before = _snap(_make_config(env={"FOO": "bar"}))
        after = _snap(_make_config(env={"FOO": "baz"}), version="v2")
        result = diff_snapshots(before, after)
        assert any(d.field == "env" for d in result.deltas)

    def test_different_services_raises(self):
        a = _snap(_make_config(name="alpha"))
        b = Snapshot(service="beta", version="v1", config=_make_config(name="beta"))
        with pytest.raises(ValueError, match="different services"):
            diff_snapshots(a, b)

    def test_custom_fields_filter(self):
        before = _snap(_make_config(image="nginx:1.0", replicas=1))
        after = _snap(_make_config(image="nginx:2.0", replicas=3), version="v2")
        result = diff_snapshots(before, after, fields=("replicas",))
        fields = [d.field for d in result.deltas]
        assert "replicas" in fields
        assert "image" not in fields
