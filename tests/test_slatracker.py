"""Tests for patchwork.slatracker."""
from __future__ import annotations

import pytest
from datetime import datetime

from patchwork.slatracker import SLAEntry, SLAError, SLAReport, SLATracker


DEFAULT_THRESHOLDS = {"api": 30.0, "worker": 60.0, "frontend": 45.0}


@pytest.fixture
def tracker() -> SLATracker:
    return SLATracker(thresholds=DEFAULT_THRESHOLDS)


class TestSLAEntry:
    def _make(self, actual: float, maximum: float) -> SLAEntry:
        return SLAEntry(
            service="api",
            max_duration_seconds=maximum,
            recorded_at=datetime(2024, 1, 1, 12, 0, 0),
            actual_duration_seconds=actual,
        )

    def test_not_breached_when_within_limit(self):
        entry = self._make(actual=20.0, maximum=30.0)
        assert entry.breached is False

    def test_breached_when_over_limit(self):
        entry = self._make(actual=35.0, maximum=30.0)
        assert entry.breached is True

    def test_not_breached_at_exact_limit(self):
        entry = self._make(actual=30.0, maximum=30.0)
        assert entry.breached is False

    def test_to_dict_contains_all_keys(self):
        entry = self._make(actual=20.0, maximum=30.0)
        d = entry.to_dict()
        assert set(d.keys()) == {
            "service", "max_duration_seconds", "recorded_at",
            "actual_duration_seconds", "breached",
        }

    def test_round_trip(self):
        entry = self._make(actual=20.0, maximum=30.0)
        restored = SLAEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.actual_duration_seconds == entry.actual_duration_seconds
        assert restored.breached == entry.breached

    def test_repr_contains_status_ok(self):
        entry = self._make(actual=10.0, maximum=30.0)
        assert "OK" in repr(entry)

    def test_repr_contains_status_breached(self):
        entry = self._make(actual=50.0, maximum=30.0)
        assert "BREACHED" in repr(entry)


class TestSLATracker:
    def test_record_returns_entry(self, tracker: SLATracker):
        entry = tracker.record("api", 20.0)
        assert entry.service == "api"
        assert entry.actual_duration_seconds == 20.0

    def test_record_unknown_service_raises(self, tracker: SLATracker):
        with pytest.raises(SLAError, match="unknown_svc"):
            tracker.record("unknown_svc", 10.0)

    def test_report_has_no_breaches_when_all_within_sla(self, tracker: SLATracker):
        tracker.record("api", 10.0)
        tracker.record("worker", 30.0)
        report = tracker.report()
        assert report.has_breaches is False

    def test_report_detects_breach(self, tracker: SLATracker):
        tracker.record("api", 50.0)  # over 30s limit
        report = tracker.report()
        assert report.has_breaches is True
        assert "api" in report.breached_services

    def test_report_summary_no_entries(self):
        t = SLATracker(thresholds={})
        assert "No SLA" in t.report().summary()

    def test_report_multiple_breaches_all_listed(self, tracker: SLATracker):
        """All breaching services should appear in breached_services."""
        tracker.record("api", 50.0)       # over 30s limit
        tracker.record("worker", 90.0)    # over 60s limit
        tracker.record("frontend", 20.0)  # within 45s limit
        report = tracker.report()
        assert report.has_breaches is True
        assert "api" in report.breached_services
        assert "worker" in report.breached_services
        assert "frontend" not in report.breached_services
