"""Tests for patchwork.healthcheck."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from patchwork.healthcheck import HealthCheckOptions, HealthChecker, HealthCheckResult
from patchwork.ssh import SSHError, CommandResult


def _make_cmd_result(stdout: str, returncode: int = 0) -> CommandResult:
    r = MagicMock(spec=CommandResult)
    r.stdout = stdout
    r.returncode = returncode
    r.ok = returncode == 0
    return r


def _make_client(responses):
    """responses: list of (stdout, returncode) or SSHError instances."""
    client = MagicMock()
    side_effects = []
    for resp in responses:
        if isinstance(resp, Exception):
            side_effects.append(resp)
        else:
            side_effects.append(_make_cmd_result(*resp))
    client.run.side_effect = side_effects
    return client


class TestHealthCheckOptions:
    def test_defaults_are_valid(self):
        opts = HealthCheckOptions()
        assert opts.retries == 3
        assert opts.retry_delay == 2.0
        assert opts.expected_output == "active"

    def test_invalid_retries_raises(self):
        with pytest.raises(ValueError, match="retries"):
            HealthCheckOptions(retries=0)

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="retry_delay"):
            HealthCheckOptions(retry_delay=-1.0)


class TestHealthChecker:
    def test_passes_on_first_attempt(self):
        client = _make_client([("active", 0)])
        opts = HealthCheckOptions(retries=3, retry_delay=0)
        checker = HealthChecker(client, opts)
        result = checker.check("myapp")
        assert result.passed is True
        assert result.attempts == 1
        assert result.service == "myapp"

    def test_passes_on_second_attempt(self):
        client = _make_client([("inactive", 1), ("active", 0)])
        opts = HealthCheckOptions(retries=3, retry_delay=0)
        checker = HealthChecker(client, opts)
        result = checker.check("myapp")
        assert result.passed is True
        assert result.attempts == 2

    def test_fails_after_all_retries(self):
        client = _make_client([("inactive", 1), ("inactive", 1), ("inactive", 1)])
        opts = HealthCheckOptions(retries=3, retry_delay=0)
        checker = HealthChecker(client, opts)
        result = checker.check("myapp")
        assert result.passed is False
        assert result.attempts == 3

    def test_ssh_error_counts_as_failure(self):
        client = _make_client([SSHError("connection refused"), SSHError("connection refused")])
        opts = HealthCheckOptions(retries=2, retry_delay=0)
        checker = HealthChecker(client, opts)
        result = checker.check("myapp")
        assert result.passed is False
        assert "connection refused" in result.message

    def test_check_many_returns_all_results(self):
        client = _make_client([("active", 0), ("active", 0)])
        opts = HealthCheckOptions(retries=1, retry_delay=0)
        checker = HealthChecker(client, opts)
        results = checker.check_many(["svc-a", "svc-b"])
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_repr_contains_service_and_status(self):
        r = HealthCheckResult(service="api", passed=True, attempts=1, message="ok")
        assert "api" in repr(r)
        assert "PASS" in repr(r)

    @patch("patchwork.healthcheck.time.sleep")
    def test_retry_delay_is_respected(self, mock_sleep):
        client = _make_client([("inactive", 1), ("active", 0)])
        opts = HealthCheckOptions(retries=3, retry_delay=1.5)
        checker = HealthChecker(client, opts)
        checker.check("myapp")
        mock_sleep.assert_called_once_with(1.5)
