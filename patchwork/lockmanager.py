"""Deployment lock manager — prevents concurrent deploys to the same service."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


class LockError(Exception):
    """Raised when a lock cannot be acquired."""

    def __repr__(self) -> str:
        return f"LockError({self.args[0]!r})"


@dataclass
class LockEntry:
    service: str
    owner: str
    acquired_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        return (now - self.acquired_at) > self.ttl_seconds

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "owner": self.owner,
            "acquired_at": self.acquired_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LockEntry":
        return cls(
            service=data["service"],
            owner=data["owner"],
            acquired_at=float(data["acquired_at"]),
            ttl_seconds=float(data["ttl_seconds"]),
        )

    def __repr__(self) -> str:
        return f"LockEntry(service={self.service!r}, owner={self.owner!r})"


class LockManager:
    """File-backed lock store for deployment services."""

    def __init__(self, store_path: Path) -> None:
        self.store_path = Path(store_path)
        self._locks: Dict[str, LockEntry] = {}
        if self.store_path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self.store_path.read_text())
        self._locks = {k: LockEntry.from_dict(v) for k, v in raw.items()}

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._locks.items()}, indent=2)
        )

    def acquire(self, service: str, owner: str, ttl_seconds: float = 300.0) -> LockEntry:
        existing = self._locks.get(service)
        if existing and not existing.is_expired():
            raise LockError(
                f"Service {service!r} is locked by {existing.owner!r}"
            )
        entry = LockEntry(service=service, owner=owner, ttl_seconds=ttl_seconds)
        self._locks[service] = entry
        self._save()
        return entry

    def release(self, service: str, owner: str) -> bool:
        entry = self._locks.get(service)
        if entry is None:
            return False
        if entry.owner != owner:
            raise LockError(
                f"Cannot release lock on {service!r}: owned by {entry.owner!r}, not {owner!r}"
            )
        del self._locks[service]
        self._save()
        return True

    def status(self) -> Dict[str, LockEntry]:
        now = time.time()
        return {k: v for k, v in self._locks.items() if not v.is_expired(now)}

    def purge_expired(self) -> int:
        now = time.time()
        expired = [k for k, v in self._locks.items() if v.is_expired(now)]
        for k in expired:
            del self._locks[k]
        if expired:
            self._save()
        return len(expired)
