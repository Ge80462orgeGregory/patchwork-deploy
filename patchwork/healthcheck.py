"""Health check module for verifying service state after deployment."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from patchwork.ssh import SSHClient, SSHError


@dataclass
class HealthCheckResult:
    service: str
    passed: bool
    attempts: int
    message: str
    output: str = ""

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"<HealthCheckResult service={self.service!r} status={status} attempts={self.attempts}>"


@dataclass
class HealthCheckOptions:
    command: str = "systemctl is-active {service}"
    retries: int = 3
    retry_delay: float = 2.0
    expected_output: str = "active"
    timeout: int = 10

    def __post_init__(self) -> None:
        if self.retries < 1:
            raise ValueError("retries must be >= 1")
        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")


class HealthChecker:
    """Runs health checks against a remote service over SSH."""

    def __init__(self, client: SSHClient, options: Optional[HealthCheckOptions] = None) -> None:
        self._client = client
        self._options = options or HealthCheckOptions()

    def check(self, service: str) -> HealthCheckResult:
        opts = self._options
        cmd = opts.command.format(service=service)
        last_output = ""
        last_error = ""

        for attempt in range(1, opts.retries + 1):
            try:
                result = self._client.run(cmd, timeout=opts.timeout)
                last_output = result.stdout.strip()
                if opts.expected_output in last_output:
                    return HealthCheckResult(
                        service=service,
                        passed=True,
                        attempts=attempt,
                        message=f"Service {service!r} is healthy.",
                        output=last_output,
                    )
            except SSHError as exc:
                last_error = str(exc)

            if attempt < opts.retries:
                time.sleep(opts.retry_delay)

        return HealthCheckResult(
            service=service,
            passed=False,
            attempts=opts.retries,
            message=f"Service {service!r} failed health check after {opts.retries} attempt(s). {last_error}".strip(),
            output=last_output,
        )

    def check_many(self, services: List[str]) -> List[HealthCheckResult]:
        return [self.check(s) for s in services]
