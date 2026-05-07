"""Feature flag manager for toggling deployment capabilities per service."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import json
import time


class FeatureFlagError(Exception):
    def __repr__(self) -> str:
        return f"FeatureFlagError({self.args[0]!r})"


@dataclass
class FeatureFlag:
    name: str
    enabled: bool
    services: List[str]  # empty list means applies to all services
    created_at: float = field(default_factory=time.time)
    description: str = ""

    def applies_to(self, service: str) -> bool:
        """Return True if this flag applies to the given service."""
        return not self.services or service in self.services

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "services": self.services,
            "created_at": self.created_at,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FeatureFlag":
        return cls(
            name=data["name"],
            enabled=data["enabled"],
            services=data.get("services", []),
            created_at=data.get("created_at", time.time()),
            description=data.get("description", ""),
        )

    def __repr__(self) -> str:
        status = "on" if self.enabled else "off"
        scope = ",".join(self.services) if self.services else "*"
        return f"FeatureFlag({self.name!r} {status} scope={scope!r})"


@dataclass
class FeatureFlagStore:
    path: Path
    _flags: Dict[str, FeatureFlag] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self.path.read_text())
        self._flags = {name: FeatureFlag.from_dict(entry) for name, entry in raw.items()}

    def _save(self) -> None:
        self.path.write_text(json.dumps({k: v.to_dict() for k, v in self._flags.items()}, indent=2))

    def set(self, flag: FeatureFlag) -> None:
        self._flags[flag.name] = flag
        self._save()

    def remove(self, name: str) -> None:
        if name not in self._flags:
            raise FeatureFlagError(f"Flag {name!r} not found")
        del self._flags[name]
        self._save()

    def is_enabled(self, name: str, service: Optional[str] = None) -> bool:
        flag = self._flags.get(name)
        if flag is None:
            return False
        if service is not None:
            return flag.enabled and flag.applies_to(service)
        return flag.enabled

    def list_flags(self) -> List[FeatureFlag]:
        return list(self._flags.values())

    def __len__(self) -> int:
        return len(self._flags)
