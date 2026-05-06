"""Change window manager — enforces deployment time restrictions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import List, Optional


class ChangeWindowError(Exception):
    def __repr__(self) -> str:
        return f"ChangeWindowError({self.args[0]!r})"


@dataclass
class ChangeWindow:
    name: str
    days: List[int]          # 0=Monday … 6=Sunday
    start: time
    end: time
    enabled: bool = True

    def allows(self, dt: Optional[datetime] = None) -> bool:
        """Return True if *dt* (default: now) falls within this window."""
        if not self.enabled:
            return True
        dt = dt or datetime.now()
        if dt.weekday() not in self.days:
            return False
        return self.start <= dt.time() <= self.end

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "days": self.days,
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChangeWindow":
        return cls(
            name=data["name"],
            days=data["days"],
            start=time.fromisoformat(data["start"]),
            end=time.fromisoformat(data["end"]),
            enabled=data.get("enabled", True),
        )

    def __repr__(self) -> str:
        return (
            f"ChangeWindow(name={self.name!r}, days={self.days}, "
            f"start={self.start}, end={self.end}, enabled={self.enabled})"
        )


@dataclass
class ChangeWindowStore:
    _path: Path
    _windows: List[ChangeWindow] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self._path.exists():
            raw = json.loads(self._path.read_text())
            self._windows = [ChangeWindow.from_dict(w) for w in raw]

    def add(self, window: ChangeWindow) -> None:
        if any(w.name == window.name for w in self._windows):
            raise ChangeWindowError(f"Window {window.name!r} already exists")
        self._windows.append(window)
        self._save()

    def remove(self, name: str) -> None:
        before = len(self._windows)
        self._windows = [w for w in self._windows if w.name != name]
        if len(self._windows) == before:
            raise ChangeWindowError(f"Window {name!r} not found")
        self._save()

    def is_deployment_allowed(self, dt: Optional[datetime] = None) -> bool:
        """Return True if at least one enabled window allows *dt*."""
        active = [w for w in self._windows if w.enabled]
        if not active:
            return True
        return any(w.allows(dt) for w in active)

    def all(self) -> List[ChangeWindow]:
        return list(self._windows)

    def _save(self) -> None:
        self._path.write_text(json.dumps([w.to_dict() for w in self._windows], indent=2))
