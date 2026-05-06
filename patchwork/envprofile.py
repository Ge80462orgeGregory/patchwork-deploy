"""Environment profile management for patchwork-deploy.

Allows named profiles (dev, staging, prod) to carry default SSH options,
environment variable overrides, and deploy constraints.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import os


class ProfileError(Exception):
    """Raised when a profile operation fails."""

    def __repr__(self) -> str:
        return f"ProfileError({self.args[0]!r})"


@dataclass
class EnvProfile:
    """A named deployment environment profile."""

    name: str
    ssh_user: str = "deploy"
    ssh_port: int = 22
    env_vars: Dict[str, str] = field(default_factory=dict)
    allowed_services: List[str] = field(default_factory=list)  # empty = all allowed
    dry_run: bool = False

    def is_service_allowed(self, service: str) -> bool:
        """Return True if the service may be deployed under this profile."""
        if not self.allowed_services:
            return True
        return service in self.allowed_services

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ssh_user": self.ssh_user,
            "ssh_port": self.ssh_port,
            "env_vars": self.env_vars,
            "allowed_services": self.allowed_services,
            "dry_run": self.dry_run,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnvProfile":
        return cls(
            name=data["name"],
            ssh_user=data.get("ssh_user", "deploy"),
            ssh_port=data.get("ssh_port", 22),
            env_vars=data.get("env_vars", {}),
            allowed_services=data.get("allowed_services", []),
            dry_run=data.get("dry_run", False),
        )

    def __repr__(self) -> str:
        return (
            f"EnvProfile(name={self.name!r}, ssh_user={self.ssh_user!r}, "
            f"dry_run={self.dry_run})"
        )


class ProfileStore:
    """Persist and retrieve EnvProfile objects from a JSON file."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._profiles: Dict[str, EnvProfile] = {}
        if os.path.exists(path):
            self._load()

    def _load(self) -> None:
        with open(self.path, "r") as fh:
            raw = json.load(fh)
        for entry in raw.get("profiles", []):
            p = EnvProfile.from_dict(entry)
            self._profiles[p.name] = p

    def _save(self) -> None:
        data = {"profiles": [p.to_dict() for p in self._profiles.values()]}
        with open(self.path, "w") as fh:
            json.dump(data, fh, indent=2)

    def save(self, profile: EnvProfile) -> None:
        self._profiles[profile.name] = profile
        self._save()

    def get(self, name: str) -> Optional[EnvProfile]:
        return self._profiles.get(name)

    def list(self) -> List[EnvProfile]:
        return list(self._profiles.values())

    def delete(self, name: str) -> bool:
        if name not in self._profiles:
            return False
        del self._profiles[name]
        self._save()
        return True

    def __len__(self) -> int:
        return len(self._profiles)
