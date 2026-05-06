"""Maintenance mode manager — pause deployments for specific services."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class MaintenanceError(Exception):
    def __repr__(self) -> str:
        return f"MaintenanceError({self.args[0]!r})"


@dataclass
class MaintenanceEntry:
    service: str
    reason: str
    enabled_at: float
    enabled_by: str
    disabled_at: Optional[float] = None

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "reason": self.reason,
            "enabled_at": self.enabled_at,
            "enabled_by": self.enabled_by,
            "disabled_at": self.disabled_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaintenanceEntry":
        return cls(
            service=data["service"],
            reason=data["reason"],
            enabled_at=data["enabled_at"],
            enabled_by=data["enabled_by"],
            disabled_at=data.get("disabled_at"),
        )

    def __repr__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return f"MaintenanceEntry(service={self.service!r}, status={status!r})"


@dataclass
class MaintenanceStore:
    path: Path
    _entries: Dict[str, MaintenanceEntry] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            self._entries = {
                k: MaintenanceEntry.from_dict(v) for k, v in raw.items()
            }

    def _save(self) -> None:
        self.path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._entries.items()}, indent=2)
        )

    def enable(self, service: str, reason: str, enabled_by: str) -> MaintenanceEntry:
        entry = MaintenanceEntry(
            service=service,
            reason=reason,
            enabled_at=time.time(),
            enabled_by=enabled_by,
        )
        self._entries[service] = entry
        self._save()
        return entry

    def disable(self, service: str) -> MaintenanceEntry:
        if service not in self._entries or not self._entries[service].is_active:
            raise MaintenanceError(f"No active maintenance for service {service!r}")
        self._entries[service].disabled_at = time.time()
        self._save()
        return self._entries[service]

    def is_under_maintenance(self, service: str) -> bool:
        entry = self._entries.get(service)
        return entry is not None and entry.is_active

    def active_entries(self) -> List[MaintenanceEntry]:
        return [e for e in self._entries.values() if e.is_active]

    def all_entries(self) -> List[MaintenanceEntry]:
        return list(self._entries.values())
