"""Rollback support: snapshot current state and restore on failure."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from patchwork.core import ServiceConfig


@dataclass
class Snapshot:
    """Point-in-time capture of a service configuration."""
    service: str
    timestamp: float
    config: ServiceConfig

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "timestamp": self.timestamp,
            "config": self.config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        return cls(
            service=data["service"],
            timestamp=data["timestamp"],
            config=ServiceConfig.from_dict(data["config"]),
        )


@dataclass
class RollbackStore:
    """Persists snapshots to a local JSON file."""
    path: Path
    _snapshots: List[Snapshot] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            self._snapshots = [Snapshot.from_dict(s) for s in raw]

    def save(self, config: ServiceConfig) -> Snapshot:
        snap = Snapshot(
            service=config.name,
            timestamp=time.time(),
            config=config,
        )
        # keep only the latest snapshot per service
        self._snapshots = [
            s for s in self._snapshots if s.service != config.name
        ]
        self._snapshots.append(snap)
        self._persist()
        return snap

    def latest(self, service: str) -> Optional[Snapshot]:
        matches = [s for s in self._snapshots if s.service == service]
        return matches[-1] if matches else None

    def remove(self, service: str) -> None:
        self._snapshots = [s for s in self._snapshots if s.service != service]
        self._persist()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([s.to_dict() for s in self._snapshots], indent=2))
