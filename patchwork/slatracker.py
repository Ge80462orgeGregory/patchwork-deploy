"""SLA tracker: monitors deployment durations against defined SLA thresholds."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


class SLAError(Exception):
    """Raised for SLA configuration or lookup errors."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"SLAError({self.args[0]!r})"


@dataclass
class SLAEntry:
    service: str
    max_duration_seconds: float
    recorded_at: datetime
    actual_duration_seconds: float
    breached: bool = field(init=False)

    def __post_init__(self) -> None:
        self.breached = self.actual_duration_seconds > self.max_duration_seconds

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "max_duration_seconds": self.max_duration_seconds,
            "recorded_at": self.recorded_at.isoformat(),
            "actual_duration_seconds": self.actual_duration_seconds,
            "breached": self.breached,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SLAEntry":
        obj = cls(
            service=data["service"],
            max_duration_seconds=data["max_duration_seconds"],
            recorded_at=datetime.fromisoformat(data["recorded_at"]),
            actual_duration_seconds=data["actual_duration_seconds"],
        )
        return obj

    def __repr__(self) -> str:
        status = "BREACHED" if self.breached else "OK"
        return (
            f"SLAEntry(service={self.service!r}, "
            f"actual={self.actual_duration_seconds:.2f}s, "
            f"max={self.max_duration_seconds:.2f}s, status={status})"
        )


@dataclass
class SLAReport:
    entries: List[SLAEntry] = field(default_factory=list)

    @property
    def has_breaches(self) -> bool:
        return any(e.breached for e in self.entries)

    @property
    def breached_services(self) -> List[str]:
        return [e.service for e in self.entries if e.breached]

    def summary(self) -> str:
        total = len(self.entries)
        breaches = len(self.breached_services)
        if total == 0:
            return "No SLA entries recorded."
        return f"{breaches}/{total} service(s) breached SLA."


class SLATracker:
    """Records and evaluates SLA compliance for deployments."""

    def __init__(self, thresholds: Dict[str, float]) -> None:
        """Args:
            thresholds: mapping of service name -> max allowed seconds.
        """
        self._thresholds = thresholds
        self._entries: List[SLAEntry] = []

    def record(self, service: str, duration_seconds: float) -> SLAEntry:
        """Record a deployment duration and evaluate SLA compliance."""
        max_dur = self._thresholds.get(service)
        if max_dur is None:
            raise SLAError(f"No SLA threshold defined for service {service!r}")
        entry = SLAEntry(
            service=service,
            max_duration_seconds=max_dur,
            recorded_at=datetime.utcnow(),
            actual_duration_seconds=duration_seconds,
        )
        self._entries.append(entry)
        return entry

    def report(self) -> SLAReport:
        return SLAReport(entries=list(self._entries))

    def clear(self) -> None:
        self._entries.clear()
