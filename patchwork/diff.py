"""Diff engine for comparing service configurations and generating deployment patches."""

from dataclasses import dataclass, field
from typing import Any

from patchwork.core import ServiceConfig, DeploymentDiff, fingerprint


@dataclass
class ConfigChange:
    """Represents a single configuration change."""
    key: str
    old_value: Any
    new_value: Any
    change_type: str  # 'added', 'removed', 'modified'

    def __repr__(self) -> str:
        if self.change_type == 'added':
            return f"+ {self.key}: {self.new_value}"
        elif self.change_type == 'removed':
            return f"- {self.key}: {self.old_value}"
        else:
            return f"~ {self.key}: {self.old_value!r} -> {self.new_value!r}"


@dataclass
class DiffResult:
    """Result of diffing two service configs."""
    service_name: str
    changes: list[ConfigChange] = field(default_factory=list)
    old_fingerprint: str = ""
    new_fingerprint: str = ""

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    def summary(self) -> str:
        if not self.has_changes:
            return f"{self.service_name}: no changes"
        added = sum(1 for c in self.changes if c.change_type == 'added')
        removed = sum(1 for c in self.changes if c.change_type == 'removed')
        modified = sum(1 for c in self.changes if c.change_type == 'modified')
        parts = []
        if added:
            parts.append(f"+{added}")
        if removed:
            parts.append(f"-{removed}")
        if modified:
            parts.append(f"~{modified}")
        return f"{self.service_name}: {', '.join(parts)}"


def diff_configs(old: ServiceConfig, new: ServiceConfig) -> DiffResult:
    """Compare two ServiceConfig objects and return a DiffResult."""
    result = DiffResult(
        service_name=new.name,
        old_fingerprint=fingerprint(old),
        new_fingerprint=fingerprint(new),
    )

    if result.old_fingerprint == result.new_fingerprint:
        return result

    old_env = old.env or {}
    new_env = new.env or {}

    for key in set(old_env) | set(new_env):
        if key not in old_env:
            result.changes.append(ConfigChange(key, None, new_env[key], 'added'))
        elif key not in new_env:
            result.changes.append(ConfigChange(key, old_env[key], None, 'removed'))
        elif old_env[key] != new_env[key]:
            result.changes.append(ConfigChange(key, old_env[key], new_env[key], 'modified'))

    if old.image != new.image:
        result.changes.append(ConfigChange('image', old.image, new.image, 'modified'))

    if old.replicas != new.replicas:
        result.changes.append(ConfigChange('replicas', old.replicas, new.replicas, 'modified'))

    return result


def build_deployment_diff(old_configs: dict[str, ServiceConfig], new_configs: dict[str, ServiceConfig]) -> DeploymentDiff:
    """Build a full DeploymentDiff from two sets of service configs."""
    to_add = [name for name in new_configs if name not in old_configs]
    to_remove = [name for name in old_configs if name not in new_configs]
    to_update = [
        name for name in new_configs
        if name in old_configs and fingerprint(old_configs[name]) != fingerprint(new_configs[name])
    ]
    return DeploymentDiff(to_add=to_add, to_remove=to_remove, to_update=to_update)
