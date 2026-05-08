"""Canary deployment manager: tracks staged rollout weights and promotion status."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json
from pathlib import Path


class CanaryError(Exception):
    def __repr__(self) -> str:
        return f"CanaryError({self.args[0]!r})"


@dataclass
class CanaryEntry:
    service: str
    baseline_weight: int
    canary_weight: int
    promoted: bool = False
    aborted: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not (0 <= self.baseline_weight <= 100):
            raise CanaryError(f"baseline_weight must be 0-100, got {self.baseline_weight}")
        if not (0 <= self.canary_weight <= 100):
            raise CanaryError(f"canary_weight must be 0-100, got {self.canary_weight}")
        if self.baseline_weight + self.canary_weight != 100:
            raise CanaryError(
                f"weights must sum to 100, got {self.baseline_weight + self.canary_weight}"
            )

    def is_active(self) -> bool:
        return not self.promoted and not self.aborted

    def to_dict(self) -> Dict:
        return {
            "service": self.service,
            "baseline_weight": self.baseline_weight,
            "canary_weight": self.canary_weight,
            "promoted": self.promoted,
            "aborted": self.aborted,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CanaryEntry":
        return cls(**data)

    def __repr__(self) -> str:
        status = "active" if self.is_active() else ("promoted" if self.promoted else "aborted")
        return f"CanaryEntry(service={self.service!r}, canary={self.canary_weight}%, status={status})"


@dataclass
class CanaryManager:
    store_path: Path
    _entries: Dict[str, CanaryEntry] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.store_path = Path(self.store_path)
        if self.store_path.exists():
            raw = json.loads(self.store_path.read_text())
            self._entries = {k: CanaryEntry.from_dict(v) for k, v in raw.items()}

    def _save(self) -> None:
        self.store_path.write_text(json.dumps({k: v.to_dict() for k, v in self._entries.items()}, indent=2))

    def create(self, service: str, canary_weight: int) -> CanaryEntry:
        if service in self._entries and self._entries[service].is_active():
            raise CanaryError(f"Active canary already exists for {service!r}")
        entry = CanaryEntry(service=service, baseline_weight=100 - canary_weight, canary_weight=canary_weight)
        self._entries[service] = entry
        self._save()
        return entry

    def promote(self, service: str) -> CanaryEntry:
        entry = self._get_active(service)
        entry.promoted = True
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return entry

    def abort(self, service: str) -> CanaryEntry:
        entry = self._get_active(service)
        entry.aborted = True
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self._save()
        return entry

    def get(self, service: str) -> Optional[CanaryEntry]:
        return self._entries.get(service)

    def list_active(self) -> List[CanaryEntry]:
        return [e for e in self._entries.values() if e.is_active()]

    def _get_active(self, service: str) -> CanaryEntry:
        entry = self._entries.get(service)
        if entry is None:
            raise CanaryError(f"No canary entry found for {service!r}")
        if not entry.is_active():
            raise CanaryError(f"Canary for {service!r} is not active")
        return entry
