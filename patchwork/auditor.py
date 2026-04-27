"""Audit log for deployment events — records what changed, when, and by whom."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class AuditEntry:
    timestamp: str
    service: str
    action: str
    status: str  # 'success' | 'failure' | 'dry_run'
    operator: str
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "service": self.service,
            "action": self.action,
            "status": self.status,
            "operator": self.operator,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        return cls(
            timestamp=data["timestamp"],
            service=data["service"],
            action=data["action"],
            status=data["status"],
            operator=data["operator"],
            details=data.get("details", ""),
        )

    def __repr__(self) -> str:
        return (
            f"AuditEntry(service={self.service!r}, action={self.action!r}, "
            f"status={self.status!r}, operator={self.operator!r})"
        )


class AuditLog:
    """Append-only audit log stored as newline-delimited JSON."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        service: str,
        action: str,
        status: str,
        operator: Optional[str] = None,
        details: str = "",
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            service=service,
            action=action,
            status=status,
            operator=operator or os.environ.get("USER", "unknown"),
            details=details,
        )
        with self.log_path.open("a") as fh:
            fh.write(json.dumps(entry.to_dict()) + "\n")
        return entry

    def read_all(self) -> List[AuditEntry]:
        if not self.log_path.exists():
            return []
        entries: List[AuditEntry] = []
        with self.log_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(AuditEntry.from_dict(json.loads(line)))
        return entries

    def read_service(self, service: str) -> List[AuditEntry]:
        return [e for e in self.read_all() if e.service == service]
