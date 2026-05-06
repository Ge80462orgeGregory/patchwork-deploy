"""Deploy history tracker — records and queries past deployment outcomes."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


class HistoryError(Exception):
    def __repr__(self) -> str:
        return f"HistoryError({self.args[0]!r})"


@dataclass
class DeployRecord:
    service: str
    environment: str
    image: str
    status: str          # 'success' | 'failure'
    timestamp: float = field(default_factory=time.time)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "environment": self.environment,
            "image": self.image,
            "status": self.status,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(data: dict) -> "DeployRecord":
        return DeployRecord(
            service=data["service"],
            environment=data["environment"],
            image=data["image"],
            status=data["status"],
            timestamp=data["timestamp"],
            notes=data.get("notes", ""),
        )

    def __repr__(self) -> str:
        return (
            f"DeployRecord(service={self.service!r}, env={self.environment!r}, "
            f"image={self.image!r}, status={self.status!r})"
        )


class DeployHistory:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._records: List[DeployRecord] = []
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self._path.read_text())
        self._records = [DeployRecord.from_dict(r) for r in raw]

    def _save(self) -> None:
        self._path.write_text(json.dumps([r.to_dict() for r in self._records], indent=2))

    def record(self, entry: DeployRecord) -> None:
        self._records.append(entry)
        self._save()

    def all(self) -> List[DeployRecord]:
        return list(self._records)

    def for_service(self, service: str) -> List[DeployRecord]:
        return [r for r in self._records if r.service == service]

    def latest(self, service: str) -> Optional[DeployRecord]:
        matches = self.for_service(service)
        return matches[-1] if matches else None

    def last_successful(self, service: str) -> Optional[DeployRecord]:
        matches = [r for r in self.for_service(service) if r.status == "success"]
        return matches[-1] if matches else None

    def __len__(self) -> int:
        return len(self._records)
