"""Circuit breaker pattern for SSH command execution."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    CLOSED = "closed"      # normal operation
    OPEN = "open"          # blocking calls
    HALF_OPEN = "half_open"  # testing recovery


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is open."""

    def __repr__(self) -> str:
        return f"CircuitOpenError({self.args[0]!r})"


@dataclass
class CircuitBreakerOptions:
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    success_threshold: int = 2

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")


@dataclass
class CircuitBreaker:
    name: str
    options: CircuitBreakerOptions = field(default_factory=CircuitBreakerOptions)

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _opened_at: Optional[float] = field(default=None, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._opened_at or 0.0)
            if elapsed >= self.options.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def allow_request(self) -> bool:
        return self.state != CircuitState.OPEN

    def record_success(self) -> None:
        state = self.state
        if state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.options.success_threshold:
                self._reset()
        elif state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        state = self.state
        if state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            self._failure_count += 1
            if self._failure_count >= self.options.failure_threshold:
                self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None

    def call(self, fn, *args, **kwargs):
        if not self.allow_request():
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
