"""Deploy gate: evaluates whether a service is cleared for deployment
based on active locks, maintenance mode, approval status, and change windows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class GateViolation:
    service: str
    reason: str
    source: str  # e.g. 'lock', 'maintenance', 'approval', 'change_window'

    def __repr__(self) -> str:
        return f"GateViolation(service={self.service!r}, source={self.source!r}, reason={self.reason!r})"

    def to_dict(self) -> dict:
        return {"service": self.service, "source": self.source, "reason": self.reason}


@dataclass
class GateResult:
    service: str
    violations: List[GateViolation] = field(default_factory=list)

    @property
    def cleared(self) -> bool:
        return len(self.violations) == 0

    def add_violation(self, source: str, reason: str) -> None:
        self.violations.append(GateViolation(self.service, reason, source))

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "cleared": self.cleared,
            "violations": [v.to_dict() for v in self.violations],
        }

    def __repr__(self) -> str:
        status = "CLEARED" if self.cleared else f"BLOCKED({len(self.violations)})"
        return f"GateResult(service={self.service!r}, status={status})"


class DeployGate:
    """Evaluates deployment readiness for one or more services."""

    def __init__(
        self,
        lock_manager=None,
        maintenance_store=None,
        approval_gate=None,
        change_window_store=None,
    ):
        self._locks = lock_manager
        self._maintenance = maintenance_store
        self._approvals = approval_gate
        self._windows = change_window_store

    def evaluate(self, service: str, now: Optional[datetime] = None) -> GateResult:
        now = now or datetime.utcnow()
        result = GateResult(service=service)

        if self._locks is not None:
            entry = self._locks.get(service)
            if entry is not None and not entry.is_expired(now):
                result.add_violation("lock", f"Service is locked: {entry.reason}")

        if self._maintenance is not None:
            entry = self._maintenance.get(service)
            if entry is not None and entry.is_active(now):
                result.add_violation("maintenance", "Service is in maintenance mode")

        if self._approvals is not None:
            entry = self._approvals.get(service)
            if entry is not None and not entry.is_approved():
                result.add_violation("approval", "Deployment has not been approved")

        if self._windows is not None:
            window = self._windows.get(service)
            if window is not None and not window.allows(now):
                result.add_violation("change_window", "Outside allowed change window")

        return result

    def evaluate_many(self, services: List[str], now: Optional[datetime] = None) -> List[GateResult]:
        return [self.evaluate(s, now) for s in services]
