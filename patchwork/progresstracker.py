"""Progress tracker for deployment pipeline steps."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProgressEntry:
    service: str
    total_steps: int
    completed: int = 0
    failed: int = 0
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None

    @property
    def is_done(self) -> bool:
        return self.completed + self.failed >= self.total_steps

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return round(end - self.started_at, 3)

    @property
    def percent(self) -> float:
        if self.total_steps == 0:
            return 100.0
        return round((self.completed + self.failed) / self.total_steps * 100, 1)

    def __repr__(self) -> str:
        return (
            f"ProgressEntry(service={self.service!r}, "
            f"{self.completed}/{self.total_steps}, "
            f"failed={self.failed}, {self.percent}%)"
        )


class ProgressTracker:
    """Tracks per-service deployment progress."""

    def __init__(self) -> None:
        self._entries: Dict[str, ProgressEntry] = {}

    def register(self, service: str, total_steps: int) -> None:
        if total_steps < 0:
            raise ValueError("total_steps must be >= 0")
        self._entries[service] = ProgressEntry(service=service, total_steps=total_steps)

    def advance(self, service: str, *, failed: bool = False) -> ProgressEntry:
        entry = self._get(service)
        if failed:
            entry.failed += 1
        else:
            entry.completed += 1
        if entry.is_done:
            entry.finished_at = time.time()
        return entry

    def get(self, service: str) -> ProgressEntry:
        return self._get(service)

    def all_done(self) -> bool:
        return all(e.is_done for e in self._entries.values())

    def summary(self) -> List[str]:
        lines = []
        for e in self._entries.values():
            status = "DONE" if e.is_done else "IN PROGRESS"
            lines.append(
                f"[{status}] {e.service}: {e.completed}/{e.total_steps} ok, "
                f"{e.failed} failed ({e.percent}%) in {e.elapsed}s"
            )
        return lines

    def _get(self, service: str) -> ProgressEntry:
        if service not in self._entries:
            raise KeyError(f"Service {service!r} not registered")
        return self._entries[service]

    def __len__(self) -> int:
        return len(self._entries)
