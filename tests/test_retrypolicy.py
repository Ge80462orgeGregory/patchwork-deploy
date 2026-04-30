"""Tests for patchwork.retrypolicy."""
import pytest
from patchwork.retrypolicy import RetryPolicy, RetryResult, RetryExhausted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _counter(successes_on: set[int]):
    """Return a callable that succeeds only on the attempt indices in *successes_on*."""
    state = {"call": 0}

    def fn() -> bool:
        result = state["call"] in successes_on
        state["call"] += 1
        return result

    return fn


def _no_sleep(seconds: float) -> None:  # noqa: ARG001
    pass


# ---------------------------------------------------------------------------
# RetryPolicy construction
# ---------------------------------------------------------------------------

class TestRetryPolicyValidation:
    def test_defaults_are_valid(self):
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.base_delay == 1.0

    def test_invalid_max_attempts_raises(self):
        with pytest.raises(ValueError, match="max_attempts"):
            RetryPolicy(max_attempts=0)

    def test_negative_base_delay_raises(self):
        with pytest.raises(ValueError, match="base_delay"):
            RetryPolicy(base_delay=-0.1)

    def test_backoff_factor_below_one_raises(self):
        with pytest.raises(ValueError, match="backoff_factor"):
            RetryPolicy(backoff_factor=0.5)

    def test_max_delay_below_base_delay_raises(self):
        with pytest.raises(ValueError, match="max_delay"):
            RetryPolicy(base_delay=5.0, max_delay=2.0)


# ---------------------------------------------------------------------------
# Delay calculation
# ---------------------------------------------------------------------------

class TestDelayFor:
    def test_first_attempt_has_no_delay(self):
        p = RetryPolicy(base_delay=2.0)
        assert p.delay_for(0) == 0.0

    def test_second_attempt_uses_base_delay(self):
        p = RetryPolicy(base_delay=2.0, backoff_factor=2.0)
        assert p.delay_for(1) == 2.0

    def test_third_attempt_doubles(self):
        p = RetryPolicy(base_delay=2.0, backoff_factor=2.0, max_delay=100.0)
        assert p.delay_for(2) == 4.0

    def test_delay_capped_at_max(self):
        p = RetryPolicy(base_delay=1.0, backoff_factor=10.0, max_delay=5.0)
        assert p.delay_for(3) == 5.0


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

class TestExecute:
    def test_succeeds_on_first_attempt(self):
        p = RetryPolicy(max_attempts=3, base_delay=0.0)
        result = p.execute(_counter({0}), sleep_fn=_no_sleep)
        assert result.succeeded is True
        assert result.total_attempts == 1

    def test_succeeds_on_second_attempt(self):
        p = RetryPolicy(max_attempts=3, base_delay=0.0)
        result = p.execute(_counter({1}), sleep_fn=_no_sleep)
        assert result.succeeded is True
        assert result.total_attempts == 2
        assert result.failed_attempts == 1

    def test_exhausts_all_attempts(self):
        p = RetryPolicy(max_attempts=3, base_delay=0.0)
        result = p.execute(_counter(set()), sleep_fn=_no_sleep)
        assert result.succeeded is False
        assert result.total_attempts == 3
        assert result.failed_attempts == 3

    def test_sleep_called_between_retries(self):
        delays: list[float] = []
        p = RetryPolicy(max_attempts=3, base_delay=1.0, backoff_factor=2.0)
        p.execute(_counter(set()), sleep_fn=delays.append)
        # First attempt: no sleep; 2nd and 3rd have delays
        assert len(delays) == 2
        assert delays[0] == 1.0
        assert delays[1] == 2.0


# ---------------------------------------------------------------------------
# RetryResult repr
# ---------------------------------------------------------------------------

class TestRetryResultRepr:
    def test_repr_success(self):
        r = RetryResult(succeeded=True, attempts=[False, True])
        assert "ok" in repr(r)
        assert "attempts=2" in repr(r)

    def test_repr_failure(self):
        r = RetryResult(succeeded=False, attempts=[False, False])
        assert "failed" in repr(r)
