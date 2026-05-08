"""Blame log: tracks who triggered each deployment and why."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


class BlameError(Exception):
    def __repr__(self) -> str:
        return f"BlameError({self.args[0]!r})"


@dataclass
class BlameEntry:
    entry_id: str
    service: str
    actor: str
    reason: str
    triggered_at: str
    commit_sha: Optional[str] = None
    ticket: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "service": self.service,
            "actor": self.actor,
            "reason": self.reason,
            "triggered_at": self.triggered_at,
            "commit_sha": self.commit_sha,
            "ticket": self.ticket,
        }

    @staticmethod
    def from_dict(data: dict) -> "BlameEntry":
        return BlameEntry(
            entry_id=data["entry_id"],
            service=data["service"],
            actor=data["actor"],
            reason=data["reason"],
            triggered_at=data["triggered_at"],
            commit_sha=data.get("commit_sha"),
            ticket=data.get("ticket"),
        )

    def __repr__(self) -> str:
        return (
            f"BlameEntry(service={self.service!r}, actor={self.actor!r}, "
            f"reason={self.reason!r}, at={self.triggered_at!r})"
        )


@dataclass
class BlameLog:
    _path: Path
    _entries: List[BlameEntry] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self._path.exists():
            raw = json.loads(self._path.read_text())
            self._entries = [BlameEntry.from_dict(r) for r in raw]

    def record(self, service: str, actor: str, reason: str,
               commit_sha: Optional[str] = None,
               ticket: Optional[str] = None) -> BlameEntry:
        entry = BlameEntry(
            entry_id=str(uuid.uuid4()),
            service=service,
            actor=actor,
            reason=reason,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            commit_sha=commit_sha,
            ticket=ticket,
        )
        self._entries.append(entry)
        self._persist()
        return entry

    def for_service(self, service: str) -> List[BlameEntry]:
        return [e for e in self._entries if e.service == service]

    def all_entries(self) -> List[BlameEntry]:
        return list(self._entries)

    def _persist(self) -> None:
        self._path.write_text(json.dumps([e.to_dict() for e in self._entries], indent=2))
