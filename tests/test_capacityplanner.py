"""Tests for patchwork.capacityplanner."""
import pytest

from patchwork.capacityplanner import (
    CapacityEntry,
    CapacityError,
    CapacityReport,
    evaluate_capacity,
)


# ---------------------------------------------------------------------------
# CapacityEntry
# ---------------------------------------------------------------------------

class TestCapacityEntry:
    def _make(self, desired=3, min_r=1, max_r=5):
        return CapacityEntry(service="svc", desired=desired, min_replicas=min_r, max_replicas=max_r)

    def test_ok_when_within_bounds(self):
        e = self._make(desired=3, min_r=1, max_r=5)
        assert not e.is_over
        assert not e.is_under

    def test_over_when_above_max(self):
        e = self._make(desired=6, min_r=1, max_r=5)
        assert e.is_over
        assert not e.is_under

    def test_under_when_below_min(self):
        e = self._make(desired=0, min_r=1, max_r=5)
        assert e.is_under
        assert not e.is_over

    def test_headroom_calculation(self):
        e = self._make(desired=3, min_r=1, max_r=5)
        assert e.headroom == 2

    def test_headroom_zero_at_max(self):
        e = self._make(desired=5, min_r=1, max_r=5)
        assert e.headroom == 0

    def test_to_dict_keys(self):
        e = self._make()
        d = e.to_dict()
        for key in ("service", "desired", "min_replicas", "max_replicas", "headroom", "is_over", "is_under"):
            assert key in d

    def test_repr_contains_service(self):
        e = self._make()
        assert "svc" in repr(e)

    def test_repr_shows_over(self):
        e = self._make(desired=10, min_r=1, max_r=5)
        assert "OVER" in repr(e)

    def test_repr_shows_under(self):
        e = self._make(desired=0, min_r=1, max_r=5)
        assert "UNDER" in repr(e)

    def test_invalid_min_replicas_raises(self):
        with pytest.raises(CapacityError):
            CapacityEntry(service="svc", desired=2, min_replicas=0, max_replicas=5)

    def test_max_less_than_min_raises(self):
        with pytest.raises(CapacityError):
            CapacityEntry(service="svc", desired=2, min_replicas=5, max_replicas=3)


# ---------------------------------------------------------------------------
# CapacityReport
# ---------------------------------------------------------------------------

class TestCapacityReport:
    def _entry(self, name, desired, min_r=1, max_r=5):
        return CapacityEntry(service=name, desired=desired, min_replicas=min_r, max_replicas=max_r)

    def test_no_violations_when_all_ok(self):
        r = CapacityReport()
        r.add(self._entry("a", 3))
        r.add(self._entry("b", 2))
        assert not r.has_violations

    def test_violations_detected(self):
        r = CapacityReport()
        r.add(self._entry("a", 3))
        r.add(self._entry("b", 6))  # over max=5
        assert r.has_violations
        assert len(r.violations) == 1

    def test_summary_contains_counts(self):
        r = CapacityReport()
        r.add(self._entry("a", 3))
        r.add(self._entry("b", 6))
        s = r.summary()
        assert "2" in s
        assert "1" in s

    def test_to_dict_structure(self):
        r = CapacityReport()
        r.add(self._entry("a", 3))
        d = r.to_dict()
        assert "entries" in d
        assert "has_violations" in d
        assert "summary" in d


# ---------------------------------------------------------------------------
# evaluate_capacity
# ---------------------------------------------------------------------------

class TestEvaluateCapacity:
    def test_basic_evaluation(self):
        configs = [{"service": "web", "replicas": 3}]
        limits = {"web": {"min_replicas": 1, "max_replicas": 5}}
        report = evaluate_capacity(configs, limits)
        assert len(report.entries) == 1
        assert not report.has_violations

    def test_over_provisioned_flagged(self):
        configs = [{"service": "web", "replicas": 10}]
        limits = {"web": {"min_replicas": 1, "max_replicas": 5}}
        report = evaluate_capacity(configs, limits)
        assert report.has_violations
        assert report.entries[0].is_over

    def test_no_limits_uses_desired_as_max(self):
        configs = [{"service": "api", "replicas": 4}]
        report = evaluate_capacity(configs)
        assert not report.has_violations

    def test_multiple_services(self):
        configs = [
            {"service": "a", "replicas": 2},
            {"service": "b", "replicas": 8},
        ]
        limits = {
            "a": {"min_replicas": 1, "max_replicas": 5},
            "b": {"min_replicas": 1, "max_replicas": 5},
        }
        report = evaluate_capacity(configs, limits)
        assert len(report.entries) == 2
        assert len(report.violations) == 1
