"""Core orchestration logic for patchwork-deploy.

Handles service config diffing and incremental deployment via SSH.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    """Represents a single service's deployment configuration."""

    name: str
    host: str
    user: str
    port: int = 22
    env: dict[str, str] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)  # remote_path -> local_path

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "ServiceConfig":
        """Construct a ServiceConfig from a raw dictionary."""
        return cls(
            name=name,
            host=data["host"],
            user=data.get("user", "deploy"),
            port=data.get("port", 22),
            env=data.get("env", {}),
            commands=data.get("commands", []),
            files=data.get("files", {}),
        )

    def fingerprint(self) -> str:
        """Return a stable hash representing the current config state."""
        payload = json.dumps(
            {
                "host": self.host,
                "user": self.user,
                "port": self.port,
                "env": self.env,
                "commands": self.commands,
                "files": self.files,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class DeploymentDiff:
    """Captures the difference between a previous and current service config."""

    service: str
    added_env: dict[str, str] = field(default_factory=dict)
    removed_env: list[str] = field(default_factory=list)
    changed_env: dict[str, str] = field(default_factory=dict)
    added_commands: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)  # remote paths

    @property
    def is_empty(self) -> bool:
        """Return True when there are no detected changes."""
        return not any(
            [
                self.added_env,
                self.removed_env,
                self.changed_env,
                self.added_commands,
                self.changed_files,
            ]
        )


def diff_configs(
    previous: ServiceConfig | None, current: ServiceConfig
) -> DeploymentDiff:
    """Compute an incremental diff between two service config versions.

    Args:
        previous: The last deployed config, or None for a fresh deployment.
        current:  The desired target config.

    Returns:
        A DeploymentDiff describing what changed.
    """
    diff = DeploymentDiff(service=current.name)

    if previous is None:
        # Treat everything as new on first deploy
        diff.added_env = dict(current.env)
        diff.added_commands = list(current.commands)
        diff.changed_files = list(current.files.keys())
        return diff

    # Env variable diff
    prev_env = previous.env
    curr_env = current.env

    for key, value in curr_env.items():
        if key not in prev_env:
            diff.added_env[key] = value
        elif prev_env[key] != value:
            diff.changed_env[key] = value

    diff.removed_env = [k for k in prev_env if k not in curr_env]

    # Commands: report any new entries appended to the list
    if current.commands != previous.commands:
        prev_set = set(previous.commands)
        diff.added_commands = [c for c in current.commands if c not in prev_set]

    # File diff: flag files whose local content hash changed
    for remote_path, local_path in current.files.items():
        prev_local = previous.files.get(remote_path)
        if prev_local != local_path or _file_changed(local_path):
            diff.changed_files.append(remote_path)

    return diff


def _file_changed(local_path: str) -> bool:
    """Return True if the local file exists and is non-empty (basic staleness check)."""
    p = Path(local_path)
    return p.exists() and p.stat().st_size > 0
