"""Rate limiter for controlling deployment frequency per service."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


class RateLimitExceeded(Exception):
    """Raised when a deployment is attempted too soon after the last one."""

    def __repr__(self) -> str:
        return f"RateLimitExceeded({self.args[0]!r})"


@dataclass
class RateLimitEntry:
    service: str
    last_deployed_at: float  # Unix timestamp
    min_interval_seconds: float

    def seconds_since_last(self, now: Optional[float] = None) -> float:
        now = now if now is not None else time.time()
        return now - self.last_deployed_at

    def is_allowed(self, now: Optional[float] = None) -> bool:
        return self.seconds_since_last(now) >= self.min_interval_seconds

    def remaining_wait(self, now: Optional[float] = None) -> float:
        remaining = self.min_interval_seconds - self.seconds_since_last(now)
        return max(0.0, remaining)


@dataclass
class RateLimiter:
    """Tracks per-service deployment timestamps and enforces minimum intervals."""

    min_interval_seconds: float = 60.0
    _entries: Dict[str, RateLimitEntry] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be non-negative")

    def check(self, service: str, now: Optional[float] = None) -> None:
        """Raise RateLimitExceeded if the service was deployed too recently."""
        now = now if now is not None else time.time()
        entry = self._entries.get(service)
        if entry is not None and not entry.is_allowed(now):
            wait = entry.remaining_wait(now)
            raise RateLimitExceeded(
                f"Service '{service}' must wait {wait:.1f}s before next deploy"
            )

    def record(self, service: str, now: Optional[float] = None) -> None:
        """Record a successful deployment for the given service."""
        now = now if now is not None else time.time()
        self._entries[service] = RateLimitEntry(
            service=service,
            last_deployed_at=now,
            min_interval_seconds=self.min_interval_seconds,
        )

    def is_allowed(self, service: str, now: Optional[float] = None) -> bool:
        """Return True if a deployment is currently allowed for the service."""
        entry = self._entries.get(service)
        if entry is None:
            return True
        return entry.is_allowed(now)

    def status(self) -> Dict[str, float]:
        """Return remaining wait seconds per tracked service (0 means allowed)."""
        now = time.time()
        return {svc: entry.remaining_wait(now) for svc, entry in self._entries.items()}
