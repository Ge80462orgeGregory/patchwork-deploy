"""Deployment quota manager — enforces per-service deployment frequency limits."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


class QuotaExceeded(Exception):
    """Raised when a service exceeds its allowed deployment quota."""

    def __repr__(self) -> str:
        return f"QuotaExceeded({self.args[0]!r})"


@dataclass
class QuotaEntry:
    service: str
    max_deploys: int          # allowed deployments per window
    window_seconds: int       # rolling window size in seconds
    deploy_times: list = field(default_factory=list)

    def record(self, ts: Optional[float] = None) -> None:
        """Record a deployment at *ts* (defaults to now)."""
        now = ts if ts is not None else time.time()
        self.deploy_times.append(now)
        self._prune(now)

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        self.deploy_times = [t for t in self.deploy_times if t > cutoff]

    def is_allowed(self, ts: Optional[float] = None) -> bool:
        now = ts if ts is not None else time.time()
        self._prune(now)
        return len(self.deploy_times) < self.max_deploys

    def remaining(self, ts: Optional[float] = None) -> int:
        now = ts if ts is not None else time.time()
        self._prune(now)
        return max(0, self.max_deploys - len(self.deploy_times))

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "max_deploys": self.max_deploys,
            "window_seconds": self.window_seconds,
            "deploy_times": self.deploy_times,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuotaEntry":
        return cls(
            service=data["service"],
            max_deploys=data["max_deploys"],
            window_seconds=data["window_seconds"],
            deploy_times=list(data.get("deploy_times", [])),
        )


class QuotaManager:
    """Persists quota entries to a JSON file and enforces limits."""

    def __init__(self, store_path: Path) -> None:
        self.store_path = Path(store_path)
        self._entries: Dict[str, QuotaEntry] = {}
        if self.store_path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self.store_path.read_text())
        for item in raw:
            e = QuotaEntry.from_dict(item)
            self._entries[e.service] = e

    def _save(self) -> None:
        data = [e.to_dict() for e in self._entries.values()]
        self.store_path.write_text(json.dumps(data, indent=2))

    def configure(self, service: str, max_deploys: int, window_seconds: int) -> QuotaEntry:
        """Create or update quota config for *service*."""
        existing = self._entries.get(service)
        times = existing.deploy_times if existing else []
        entry = QuotaEntry(service, max_deploys, window_seconds, list(times))
        self._entries[service] = entry
        self._save()
        return entry

    def check_and_record(self, service: str, ts: Optional[float] = None) -> QuotaEntry:
        """Check quota and record deployment; raise QuotaExceeded if over limit."""
        entry = self._entries.get(service)
        if entry is None:
            raise KeyError(f"No quota configured for service {service!r}")
        if not entry.is_allowed(ts):
            raise QuotaExceeded(
                f"{service!r} exceeded {entry.max_deploys} deploys "
                f"in {entry.window_seconds}s window"
            )
        entry.record(ts)
        self._save()
        return entry

    def status(self) -> Dict[str, dict]:
        return {name: e.to_dict() for name, e in self._entries.items()}
