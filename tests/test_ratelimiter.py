"""Tests for patchwork.ratelimiter."""
import pytest

from patchwork.ratelimiter import RateLimiter, RateLimitExceeded, RateLimitEntry


# ---------------------------------------------------------------------------
# RateLimitEntry
# ---------------------------------------------------------------------------

class TestRateLimitEntry:
    def _make(self, last: float, interval: float) -> RateLimitEntry:
        return RateLimitEntry(service="svc", last_deployed_at=last, min_interval_seconds=interval)

    def test_is_allowed_when_enough_time_passed(self):
        entry = self._make(last=0.0, interval=30.0)
        assert entry.is_allowed(now=31.0) is True

    def test_is_not_allowed_when_too_soon(self):
        entry = self._make(last=100.0, interval=60.0)
        assert entry.is_allowed(now=120.0) is False

    def test_is_allowed_at_exact_boundary(self):
        entry = self._make(last=100.0, interval=60.0)
        assert entry.is_allowed(now=160.0) is True

    def test_remaining_wait_positive_when_blocked(self):
        entry = self._make(last=100.0, interval=60.0)
        assert entry.remaining_wait(now=130.0) == pytest.approx(30.0)

    def test_remaining_wait_zero_when_allowed(self):
        entry = self._make(last=0.0, interval=10.0)
        assert entry.remaining_wait(now=20.0) == 0.0


# ---------------------------------------------------------------------------
# RateLimiter construction
# ---------------------------------------------------------------------------

class TestRateLimiterInit:
    def test_default_interval(self):
        rl = RateLimiter()
        assert rl.min_interval_seconds == 60.0

    def test_custom_interval(self):
        rl = RateLimiter(min_interval_seconds=120.0)
        assert rl.min_interval_seconds == 120.0

    def test_negative_interval_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            RateLimiter(min_interval_seconds=-1.0)

    def test_zero_interval_is_valid(self):
        rl = RateLimiter(min_interval_seconds=0.0)
        assert rl.min_interval_seconds == 0.0


# ---------------------------------------------------------------------------
# RateLimiter behaviour
# ---------------------------------------------------------------------------

class TestRateLimiterCheck:
    def test_first_deploy_always_allowed(self):
        rl = RateLimiter(min_interval_seconds=300.0)
        # Should not raise
        rl.check("web", now=1000.0)

    def test_check_raises_when_too_soon(self):
        rl = RateLimiter(min_interval_seconds=60.0)
        rl.record("web", now=1000.0)
        with pytest.raises(RateLimitExceeded, match="web"):
            rl.check("web", now=1030.0)

    def test_check_passes_after_interval(self):
        rl = RateLimiter(min_interval_seconds=60.0)
        rl.record("web", now=1000.0)
        rl.check("web", now=1061.0)  # Should not raise

    def test_is_allowed_unknown_service(self):
        rl = RateLimiter()
        assert rl.is_allowed("unknown") is True

    def test_is_allowed_false_when_blocked(self):
        rl = RateLimiter(min_interval_seconds=60.0)
        rl.record("api", now=500.0)
        assert rl.is_allowed("api", now=510.0) is False

    def test_is_allowed_true_after_wait(self):
        rl = RateLimiter(min_interval_seconds=60.0)
        rl.record("api", now=500.0)
        assert rl.is_allowed("api", now=561.0) is True

    def test_status_returns_remaining_per_service(self):
        rl = RateLimiter(min_interval_seconds=100.0)
        rl.record("svc-a", now=0.0)
        rl.record("svc-b", now=0.0)
        status = rl.status()
        # Both should have some remaining wait (called very close to record time)
        assert "svc-a" in status
        assert "svc-b" in status

    def test_rate_limit_exceeded_repr(self):
        exc = RateLimitExceeded("too soon")
        assert "RateLimitExceeded" in repr(exc)
