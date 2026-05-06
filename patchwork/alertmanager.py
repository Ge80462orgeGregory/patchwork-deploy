"""Alert manager: tracks firing alerts per service with severity levels."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    service: str
    message: str
    severity: Severity
    fired_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    def resolve(self) -> None:
        self.resolved_at = time.time()

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "message": self.message,
            "severity": self.severity.value,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        return cls(
            service=data["service"],
            message=data["message"],
            severity=Severity(data["severity"]),
            fired_at=data["fired_at"],
            resolved_at=data.get("resolved_at"),
        )

    def __repr__(self) -> str:
        status = "resolved" if self.is_resolved else "firing"
        return f"<Alert service={self.service!r} severity={self.severity.value} status={status}>"


class AlertManagerError(Exception):
    pass


class AlertManager:
    """Persist and query alerts for services."""

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._alerts: List[Alert] = []
        if store_path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self._path.read_text())
        self._alerts = [Alert.from_dict(a) for a in raw]

    def _save(self) -> None:
        self._path.write_text(json.dumps([a.to_dict() for a in self._alerts], indent=2))

    def fire(self, service: str, message: str, severity: Severity = Severity.WARNING) -> Alert:
        alert = Alert(service=service, message=message, severity=severity)
        self._alerts.append(alert)
        self._save()
        return alert

    def resolve(self, service: str, message: str) -> int:
        count = 0
        for alert in self._alerts:
            if alert.service == service and alert.message == message and not alert.is_resolved:
                alert.resolve()
                count += 1
        if count:
            self._save()
        return count

    def active_for(self, service: str) -> List[Alert]:
        return [a for a in self._alerts if a.service == service and not a.is_resolved]

    def all_active(self) -> List[Alert]:
        return [a for a in self._alerts if not a.is_resolved]

    def history(self, service: Optional[str] = None) -> List[Alert]:
        if service:
            return [a for a in self._alerts if a.service == service]
        return list(self._alerts)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {s.value: 0 for s in Severity}
        for alert in self.all_active():
            counts[alert.severity.value] += 1
        return counts
