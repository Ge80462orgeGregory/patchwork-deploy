"""Retry policy for deployment steps with configurable backoff."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __repr__(self) -> str:
        return f"RetryExhausted({self.args[0]!r})"


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 30.0
    jitter: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be >= 1.0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")

    def delay_for(self, attempt: int) -> float:
        """Return the delay in seconds before the given attempt (0-indexed)."""
        if attempt == 0:
            return 0.0
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        delay = min(delay, self.max_delay)
        if self.jitter:
            import random
            delay *= random.uniform(0.5, 1.0)
        return delay

    def execute(
        self,
        fn: Callable[[], bool],
        *,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> RetryResult:
        """Execute *fn* up to max_attempts times. Returns a RetryResult."""
        _sleep = sleep_fn if sleep_fn is not None else time.sleep
        attempts: list[bool] = []
        for attempt in range(self.max_attempts):
            delay = self.delay_for(attempt)
            if delay > 0:
                _sleep(delay)
            success = fn()
            attempts.append(success)
            if success:
                return RetryResult(succeeded=True, attempts=attempts)
        return RetryResult(succeeded=False, attempts=attempts)


@dataclass
class RetryResult:
    succeeded: bool
    attempts: list[bool] = field(default_factory=list)

    @property
    def total_attempts(self) -> int:
        return len(self.attempts)

    @property
    def failed_attempts(self) -> int:
        return sum(1 for a in self.attempts if not a)

    def __repr__(self) -> str:
        status = "ok" if self.succeeded else "failed"
        return (
            f"RetryResult({status}, "
            f"attempts={self.total_attempts}, "
            f"failed={self.failed_attempts})"
        )
