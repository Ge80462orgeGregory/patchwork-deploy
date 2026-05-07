"""Service registry — tracks registered services with metadata and lookup helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import pathlib


class RegistryError(Exception):
    def __repr__(self) -> str:
        return f"RegistryError({self.args[0]!r})"


@dataclass
class ServiceEntry:
    name: str
    owner: str
    tier: str  # e.g. "frontend", "backend", "data"
    tags: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "owner": self.owner,
            "tier": self.tier,
            "tags": self.tags,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceEntry":
        return cls(
            name=data["name"],
            owner=data["owner"],
            tier=data["tier"],
            tags=data.get("tags", {}),
            enabled=data.get("enabled", True),
        )

    def __repr__(self) -> str:
        return f"ServiceEntry(name={self.name!r}, tier={self.tier!r}, owner={self.owner!r})"


class ServiceRegistry:
    def __init__(self, store_path: pathlib.Path) -> None:
        self._path = store_path
        self._entries: Dict[str, ServiceEntry] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self._path.read_text())
        self._entries = {k: ServiceEntry.from_dict(v) for k, v in raw.items()}

    def _save(self) -> None:
        self._path.write_text(json.dumps({k: v.to_dict() for k, v in self._entries.items()}, indent=2))

    def register(self, entry: ServiceEntry) -> None:
        self._entries[entry.name] = entry
        self._save()

    def deregister(self, name: str) -> None:
        if name not in self._entries:
            raise RegistryError(f"Service {name!r} not found")
        del self._entries[name]
        self._save()

    def get(self, name: str) -> Optional[ServiceEntry]:
        return self._entries.get(name)

    def list_all(self) -> List[ServiceEntry]:
        return list(self._entries.values())

    def by_tier(self, tier: str) -> List[ServiceEntry]:
        return [e for e in self._entries.values() if e.tier == tier]

    def by_owner(self, owner: str) -> List[ServiceEntry]:
        return [e for e in self._entries.values() if e.owner == owner]

    def enabled_services(self) -> List[ServiceEntry]:
        return [e for e in self._entries.values() if e.enabled]

    def __len__(self) -> int:
        return len(self._entries)
