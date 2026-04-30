"""Tests for patchwork.circuitbreaker."""
import time
import pytest

from patchwork.circuitbreaker import (
    CircuitBreaker,
    CircuitBreakerOptions,
    CircuitOpenError,
    CircuitState,
)


# ---------------------------------------------------------------------------
# Options validation
# ---------------------------------------------------------------------------

class TestCircuitBreakerOptions:
    def test_defaults_are_valid(self):
        opts = CircuitBreakerOptions()
        assert opts.failure_threshold == 3
        assert opts.recovery_timeout == 30.0
        assert opts.success_threshold == 2

    def test_invalid_failure_threshold_raises(self):
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreakerOptions(failure_threshold=0)

    def test_invalid_recovery_timeout_raises(self):
        with pytest.raises(ValueError, match="recovery_timeout"):
            CircuitBreakerOptions(recovery_timeout=0)

    def test_invalid_success_threshold_raises(self):
        with pytest.raises(ValueError, match="success_threshold"):
            CircuitBreakerOptions(success_threshold=0)


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

def _breaker(failures=2, recovery=30.0, successes=2):
    opts = CircuitBreakerOptions(
        failure_threshold=failures,
        recovery_timeout=recovery,
        success_threshold=successes,
    )
    return CircuitBreaker(name="test", options=opts)


class TestCircuitBreakerStates:
    def test_initial_state_is_closed(self):
        cb = _breaker()
        assert cb.state == CircuitState.CLOSED

    def test_trips_after_threshold_failures(self):
        cb = _breaker(failures=2)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count_when_closed(self):
        cb = _breaker(failures=2)
        cb.record_failure()
        cb.record_success()
        cb.record_failure()  # counter was reset, so still closed
        assert cb.state == CircuitState.CLOSED

    def test_open_circuit_blocks_requests(self):
        cb = _breaker(failures=1)
        cb.record_failure()
        assert not cb.allow_request()

    def test_transitions_to_half_open_after_timeout(self, monkeypatch):
        cb = _breaker(failures=1, recovery=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_after_enough_successes(self, monkeypatch):
        cb = _breaker(failures=1, recovery=0.01, successes=2)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        cb = _breaker(failures=1, recovery=0.01)
        cb.record_failure()
        time.sleep(0.02)
        _ = cb.state  # trigger HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# call() helper
# ---------------------------------------------------------------------------

class TestCircuitBreakerCall:
    def test_call_returns_result_on_success(self):
        cb = _breaker()
        result = cb.call(lambda: 42)
        assert result == 42

    def test_call_raises_circuit_open_error_when_open(self):
        cb = _breaker(failures=1)
        cb.record_failure()
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: None)

    def test_call_records_failure_on_exception(self):
        cb = _breaker(failures=2)
        def boom():
            raise RuntimeError("oops")
        with pytest.raises(RuntimeError):
            cb.call(boom)
        assert cb._failure_count == 1

    def test_circuit_open_error_repr(self):
        err = CircuitOpenError("test circuit")
        assert "test circuit" in repr(err)
