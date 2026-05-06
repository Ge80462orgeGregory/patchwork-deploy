"""Service map: tracks hostname-to-service assignments and provides lookup utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import pathlib


class ServiceMapError(Exception):
    def __repr__(self) -> str:
        return f"ServiceMapError({self.args[0]!r})"


@dataclass
class ServiceEntry:
    service: str
    host: str
    environment: str
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "host": self.host,
            "environment": self.environment,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceEntry":
        return cls(
            service=data["service"],
            host=data["host"],
            environment=data["environment"],
            tags=data.get("tags", {}),
        )

    def __repr__(self) -> str:
        return f"ServiceEntry(service={self.service!r}, host={self.host!r}, env={self.environment!r})"


@dataclass
class ServiceMap:
    _entries: List[ServiceEntry] = field(default_factory=list)

    def register(self, entry: ServiceEntry) -> None:
        for i, existing in enumerate(self._entries):
            if existing.service == entry.service and existing.host == entry.host:
                self._entries[i] = entry
                return
        self._entries.append(entry)

    def by_service(self, service: str) -> List[ServiceEntry]:
        return [e for e in self._entries if e.service == service]

    def by_host(self, host: str) -> List[ServiceEntry]:
        return [e for e in self._entries if e.host == host]

    def by_environment(self, environment: str) -> List[ServiceEntry]:
        return [e for e in self._entries if e.environment == environment]

    def lookup(self, service: str, host: str) -> Optional[ServiceEntry]:
        for e in self._entries:
            if e.service == service and e.host == host:
                return e
        return None

    def remove(self, service: str, host: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if not (e.service == service and e.host == host)]
        return len(self._entries) < before

    def __len__(self) -> int:
        return len(self._entries)

    def save(self, path: pathlib.Path) -> None:
        path.write_text(json.dumps([e.to_dict() for e in self._entries], indent=2))

    @classmethod
    def load(cls, path: pathlib.Path) -> "ServiceMap":
        if not path.exists():
            raise ServiceMapError(f"Service map file not found: {path}")
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ServiceMapError(f"Invalid JSON in service map: {exc}") from exc
        sm = cls()
        for item in data:
            sm.register(ServiceEntry.from_dict(item))
        return sm
