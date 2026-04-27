"""Builds a DeployPlan from a DiffResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .diff import DiffResult


@dataclass
class DeployStep:
    description: str
    command: str
    critical: bool = True

    def __repr__(self) -> str:
        flag = " [critical]" if self.critical else ""
        return f"<DeployStep{flag} {self.description!r}>"


@dataclass
class DeployPlan:
    service: str
    steps: List[DeployStep] = field(default_factory=list)

    def add_step(self, description: str, command: str, critical: bool = True) -> None:
        self.steps.append(
            DeployStep(description=description, command=command, critical=critical)
        )

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        return f"<DeployPlan service={self.service!r} steps={len(self)}>"


def build_plan(diff: DiffResult, service_name: str) -> DeployPlan:
    """Translate a DiffResult into an ordered DeployPlan."""
    plan = DeployPlan(service=service_name)

    if not diff.has_changes():
        return plan

    for change in diff.changes:
        field_name = change.field

        if field_name == "image":
            plan.add_step(
                description=f"Pull new image {change.new_value}",
                command=f"docker pull {change.new_value}",
                critical=True,
            )
            plan.add_step(
                description=f"Restart service {service_name} with {change.new_value}",
                command=(
                    f"docker service update --image {change.new_value} {service_name}"
                ),
                critical=True,
            )

        elif field_name == "replicas":
            plan.add_step(
                description=(
                    f"Scale {service_name} to {change.new_value} replicas"
                ),
                command=(
                    f"docker service scale {service_name}={change.new_value}"
                ),
                critical=False,
            )

        elif field_name == "env":
            env_args = " ".join(
                f"--env-add {k}={v}"
                for k, v in (change.new_value or {}).items()
            )
            plan.add_step(
                description=f"Update env vars for {service_name}",
                command=f"docker service update {env_args} {service_name}",
                critical=False,
            )

        else:
            plan.add_step(
                description=f"Apply change to {field_name} for {service_name}",
                command=f"# manual update required for field '{field_name}'",
                critical=False,
            )

    return plan
