"""Dependency-aware deployment lock: prevents deploying a service
if any of its declared dependencies are currently locked or in-flight."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class DependencyLockError(Exception):
    """Raised when a dependency lock conflict is detected."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"DependencyLockError({self.args[0]!r})"


@dataclass
class DependencyLockEntry:
    service: str
    locked_by: str
    locked_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300

    def is_expired(self) -> bool:
        return (time.time() - self.locked_at) > self.ttl_seconds

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "locked_by": self.locked_by,
            "locked_at": self.locked_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @staticmethod
    def from_dict(data: dict) -> "DependencyLockEntry":
        return DependencyLockEntry(
            service=data["service"],
            locked_by=data["locked_by"],
            locked_at=data["locked_at"],
            ttl_seconds=data["ttl_seconds"],
        )

    def __repr__(self) -> str:
        return (
            f"DependencyLockEntry(service={self.service!r}, "
            f"locked_by={self.locked_by!r}, expired={self.is_expired()})"
        )


class DependencyLockManager:
    """Persists and checks dependency locks across services."""

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._locks: Dict[str, DependencyLockEntry] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self._path.read_text())
        self._locks = {
            k: DependencyLockEntry.from_dict(v) for k, v in raw.items()
        }

    def _save(self) -> None:
        self._path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._locks.items()}, indent=2)
        )

    def acquire(self, service: str, locked_by: str, ttl_seconds: int = 300) -> DependencyLockEntry:
        self._prune_expired()
        if service in self._locks:
            raise DependencyLockError(
                f"Service '{service}' is already locked by '{self._locks[service].locked_by}'"
            )
        entry = DependencyLockEntry(service=service, locked_by=locked_by, ttl_seconds=ttl_seconds)
        self._locks[service] = entry
        self._save()
        return entry

    def release(self, service: str) -> bool:
        removed = self._locks.pop(service, None)
        if removed is not None:
            self._save()
            return True
        return False

    def check_dependencies(self, dependencies: List[str]) -> List[str]:
        """Return list of dependency services that are currently locked."""
        self._prune_expired()
        return [dep for dep in dependencies if dep in self._locks]

    def _prune_expired(self) -> None:
        expired = [k for k, v in self._locks.items() if v.is_expired()]
        for k in expired:
            del self._locks[k]
        if expired:
            self._save()

    def all_locks(self) -> List[DependencyLockEntry]:
        self._prune_expired()
        return list(self._locks.values())
