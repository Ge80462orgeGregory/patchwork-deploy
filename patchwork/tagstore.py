"""Deployment tag store — attach arbitrary key/value metadata to deployments."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


class TagError(Exception):
    """Raised when a tag operation fails."""


@dataclass
class DeploymentTag:
    service: str
    deploy_id: str
    tags: Dict[str, str]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "deploy_id": self.deploy_id,
            "tags": self.tags,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "DeploymentTag":
        return DeploymentTag(
            service=data["service"],
            deploy_id=data["deploy_id"],
            tags=data["tags"],
            created_at=data["created_at"],
        )

    def __repr__(self) -> str:
        return (
            f"DeploymentTag(service={self.service!r}, "
            f"deploy_id={self.deploy_id!r}, tags={self.tags!r})"
        )


@dataclass
class TagStore:
    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> List[dict]:
        if not self.path.exists():
            return []
        with self.path.open() as fh:
            return json.load(fh)

    def _save(self, records: List[dict]) -> None:
        with self.path.open("w") as fh:
            json.dump(records, fh, indent=2)

    def put(self, tag: DeploymentTag) -> None:
        records = self._load()
        records.append(tag.to_dict())
        self._save(records)

    def get(self, service: str, deploy_id: str) -> Optional[DeploymentTag]:
        for rec in self._load():
            if rec["service"] == service and rec["deploy_id"] == deploy_id:
                return DeploymentTag.from_dict(rec)
        return None

    def list_for_service(self, service: str) -> List[DeploymentTag]:
        return [
            DeploymentTag.from_dict(r)
            for r in self._load()
            if r["service"] == service
        ]

    def find_by_tag(self, key: str, value: str) -> List[DeploymentTag]:
        return [
            DeploymentTag.from_dict(r)
            for r in self._load()
            if r["tags"].get(key) == value
        ]

    def delete(self, service: str, deploy_id: str) -> bool:
        records = self._load()
        filtered = [
            r for r in records
            if not (r["service"] == service and r["deploy_id"] == deploy_id)
        ]
        if len(filtered) == len(records):
            return False
        self._save(filtered)
        return True
