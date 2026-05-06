"""Approval gate — require explicit sign-off before a deploy plan executes."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class ApprovalError(Exception):
    """Raised when an approval operation fails."""

    def __repr__(self) -> str:
        return f"ApprovalError({self.args[0]!r})"


@dataclass
class ApprovalEntry:
    service: str
    requested_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    denied: bool = False
    created_at: float = field(default_factory=time.time)

    def is_approved(self) -> bool:
        return self.approved_by is not None and not self.denied

    def is_pending(self) -> bool:
        return self.approved_by is None and not self.denied

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "denied": self.denied,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "ApprovalEntry":
        return ApprovalEntry(
            service=data["service"],
            requested_by=data["requested_by"],
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            denied=data.get("denied", False),
            created_at=data.get("created_at", time.time()),
        )

    def __repr__(self) -> str:
        status = "approved" if self.is_approved() else ("denied" if self.denied else "pending")
        return f"ApprovalEntry(service={self.service!r}, status={status!r}, by={self.approved_by!r})"


class ApprovalGate:
    """Persisted approval gate backed by a JSON file."""

    def __init__(self, store_path: Path) -> None:
        self._path = Path(store_path)
        self._entries: Dict[str, ApprovalEntry] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        raw: List[dict] = json.loads(self._path.read_text())
        self._entries = {r["service"]: ApprovalEntry.from_dict(r) for r in raw}

    def _save(self) -> None:
        self._path.write_text(json.dumps([e.to_dict() for e in self._entries.values()], indent=2))

    def request(self, service: str, requested_by: str) -> ApprovalEntry:
        if service in self._entries and self._entries[service].is_pending():
            raise ApprovalError(f"Approval already pending for {service!r}")
        entry = ApprovalEntry(service=service, requested_by=requested_by)
        self._entries[service] = entry
        self._save()
        return entry

    def approve(self, service: str, approved_by: str) -> ApprovalEntry:
        entry = self._entries.get(service)
        if entry is None:
            raise ApprovalError(f"No approval request found for {service!r}")
        if not entry.is_pending():
            raise ApprovalError(f"Approval for {service!r} is not in pending state")
        entry.approved_by = approved_by
        entry.approved_at = time.time()
        self._save()
        return entry

    def deny(self, service: str) -> ApprovalEntry:
        entry = self._entries.get(service)
        if entry is None:
            raise ApprovalError(f"No approval request found for {service!r}")
        entry.denied = True
        self._save()
        return entry

    def status(self, service: str) -> Optional[ApprovalEntry]:
        return self._entries.get(service)

    def all_entries(self) -> List[ApprovalEntry]:
        return list(self._entries.values())

    def is_approved(self, service: str) -> bool:
        entry = self._entries.get(service)
        return entry is not None and entry.is_approved()
