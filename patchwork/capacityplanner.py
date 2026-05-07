"""Capacity planner: tracks replica headroom and flags over/under-provisioned services."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class CapacityError(Exception):
    """Raised when capacity constraints are violated."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"CapacityError({self.args[0]!r})"


@dataclass
class CapacityEntry:
    service: str
    desired: int
    min_replicas: int
    max_replicas: int

    def __post_init__(self) -> None:
        if self.min_replicas < 1:
            raise CapacityError("min_replicas must be >= 1")
        if self.max_replicas < self.min_replicas:
            raise CapacityError("max_replicas must be >= min_replicas")

    @property
    def is_over(self) -> bool:
        return self.desired > self.max_replicas

    @property
    def is_under(self) -> bool:
        return self.desired < self.min_replicas

    @property
    def headroom(self) -> int:
        """Remaining capacity before hitting max_replicas."""
        return self.max_replicas - self.desired

    def to_dict(self) -> Dict:
        return {
            "service": self.service,
            "desired": self.desired,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "headroom": self.headroom,
            "is_over": self.is_over,
            "is_under": self.is_under,
        }

    def __repr__(self) -> str:
        status = "OK"
        if self.is_over:
            status = "OVER"
        elif self.is_under:
            status = "UNDER"
        return f"CapacityEntry(service={self.service!r}, desired={self.desired}, status={status})"


@dataclass
class CapacityReport:
    entries: List[CapacityEntry] = field(default_factory=list)

    def add(self, entry: CapacityEntry) -> None:
        self.entries.append(entry)

    @property
    def violations(self) -> List[CapacityEntry]:
        return [e for e in self.entries if e.is_over or e.is_under]

    @property
    def has_violations(self) -> bool:
        return bool(self.violations)

    def summary(self) -> str:
        total = len(self.entries)
        v = len(self.violations)
        return f"{total} service(s) checked; {v} violation(s) found."

    def to_dict(self) -> Dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "has_violations": self.has_violations,
            "summary": self.summary(),
        }


def evaluate_capacity(
    configs: List[Dict],
    limits: Optional[Dict[str, Dict]] = None,
) -> CapacityReport:
    """Build a CapacityReport from a list of service config dicts.

    Each config dict should have 'service', 'replicas' keys.
    limits maps service name -> {min_replicas, max_replicas}.
    """
    limits = limits or {}
    report = CapacityReport()
    for cfg in configs:
        name = cfg["service"]
        desired = cfg.get("replicas", 1)
        bounds = limits.get(name, {})
        min_r = bounds.get("min_replicas", 1)
        max_r = bounds.get("max_replicas", desired)
        entry = CapacityEntry(
            service=name,
            desired=desired,
            min_replicas=min_r,
            max_replicas=max(max_r, min_r),
        )
        report.add(entry)
    return report
