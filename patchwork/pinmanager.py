"""Pin manager: lock a service to a specific image/version to prevent drift updates."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class PinError(Exception):
    def __repr__(self) -> str:
        return f"PinError({self.args[0]!r})"


@dataclass
class PinEntry:
    service: str
    pinned_image: str
    reason: str
    pinned_by: str
    pinned_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "pinned_image": self.pinned_image,
            "reason": self.reason,
            "pinned_by": self.pinned_by,
            "pinned_at": self.pinned_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PinEntry":
        return cls(
            service=data["service"],
            pinned_image=data["pinned_image"],
            reason=data["reason"],
            pinned_by=data["pinned_by"],
            pinned_at=data["pinned_at"],
        )

    def __repr__(self) -> str:
        return (
            f"PinEntry(service={self.service!r}, image={self.pinned_image!r}, "
            f"by={self.pinned_by!r})"
        )


@dataclass
class PinManager:
    store_path: Path
    _pins: Dict[str, PinEntry] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.store_path = Path(self.store_path)
        if self.store_path.exists():
            raw = json.loads(self.store_path.read_text())
            for entry in raw.get("pins", []):
                p = PinEntry.from_dict(entry)
                self._pins[p.service] = p

    def _save(self) -> None:
        self.store_path.write_text(
            json.dumps({"pins": [p.to_dict() for p in self._pins.values()]}, indent=2)
        )

    def pin(self, service: str, image: str, reason: str, pinned_by: str) -> PinEntry:
        entry = PinEntry(service=service, pinned_image=image, reason=reason, pinned_by=pinned_by)
        self._pins[service] = entry
        self._save()
        return entry

    def unpin(self, service: str) -> None:
        if service not in self._pins:
            raise PinError(f"Service {service!r} is not pinned")
        del self._pins[service]
        self._save()

    def is_pinned(self, service: str) -> bool:
        return service in self._pins

    def get(self, service: str) -> Optional[PinEntry]:
        return self._pins.get(service)

    def all_pins(self) -> List[PinEntry]:
        return list(self._pins.values())

    def __len__(self) -> int:
        return len(self._pins)
