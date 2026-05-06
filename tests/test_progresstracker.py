"""Tests for patchwork.progresstracker."""
import time
import pytest
from patchwork.progresstracker import ProgressEntry, ProgressTracker


# ---------------------------------------------------------------------------
# ProgressEntry
# ---------------------------------------------------------------------------
class TestProgressEntry:
    def _make(self, total=4, completed=0, failed=0):
        e = ProgressEntry(service="svc", total_steps=total)
        e.completed = completed
        e.failed = failed
        return e

    def test_not_done_initially(self):
        e = self._make(total=3)
        assert not e.is_done

    def test_done_when_all_completed(self):
        e = self._make(total=3, completed=3)
        assert e.is_done

    def test_done_when_all_failed(self):
        e = self._make(total=2, failed=2)
        assert e.is_done

    def test_done_when_mixed(self):
        e = self._make(total=4, completed=2, failed=2)
        assert e.is_done

    def test_percent_zero_steps(self):
        e = self._make(total=0)
        assert e.percent == 100.0

    def test_percent_partial(self):
        e = self._make(total=4, completed=2)
        assert e.percent == 50.0

    def test_elapsed_increases(self):
        e = self._make()
        time.sleep(0.05)
        assert e.elapsed >= 0.04

    def test_repr_contains_service(self):
        e = self._make(total=2, completed=1)
        assert "svc" in repr(e)
        assert "50.0%" in repr(e)


# ---------------------------------------------------------------------------
# ProgressTracker
# ---------------------------------------------------------------------------
class TestProgressTracker:
    def test_register_and_get(self):
        t = ProgressTracker()
        t.register("api", 5)
        e = t.get("api")
        assert e.total_steps == 5
        assert e.completed == 0

    def test_advance_ok(self):
        t = ProgressTracker()
        t.register("api", 3)
        t.advance("api")
        assert t.get("api").completed == 1

    def test_advance_failed(self):
        t = ProgressTracker()
        t.register("api", 3)
        t.advance("api", failed=True)
        assert t.get("api").failed == 1

    def test_all_done_false_initially(self):
        t = ProgressTracker()
        t.register("api", 2)
        assert not t.all_done()

    def test_all_done_true_after_completion(self):
        t = ProgressTracker()
        t.register("api", 2)
        t.advance("api")
        t.advance("api")
        assert t.all_done()

    def test_all_done_with_multiple_services(self):
        t = ProgressTracker()
        t.register("a", 1)
        t.register("b", 1)
        t.advance("a")
        assert not t.all_done()
        t.advance("b")
        assert t.all_done()

    def test_get_unknown_service_raises(self):
        t = ProgressTracker()
        with pytest.raises(KeyError):
            t.get("missing")

    def test_negative_steps_raises(self):
        t = ProgressTracker()
        with pytest.raises(ValueError):
            t.register("svc", -1)

    def test_len(self):
        t = ProgressTracker()
        t.register("a", 1)
        t.register("b", 2)
        assert len(t) == 2

    def test_summary_contains_service_name(self):
        t = ProgressTracker()
        t.register("worker", 4)
        t.advance("worker")
        lines = t.summary()
        assert len(lines) == 1
        assert "worker" in lines[0]
        assert "IN PROGRESS" in lines[0]

    def test_summary_done_status(self):
        t = ProgressTracker()
        t.register("db", 1)
        t.advance("db")
        lines = t.summary()
        assert "DONE" in lines[0]
