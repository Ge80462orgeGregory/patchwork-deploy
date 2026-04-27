"""Deployment planner: turns a DiffResult into ordered SSH commands."""

from dataclasses import dataclass, field
from typing import Callable

from patchwork.core import ServiceConfig
from patchwork.diff import DiffResult, build_deployment_diff


@dataclass
class DeployStep:
    """A single deployment step with a description and command."""
    description: str
    command: str
    critical: bool = True


@dataclass
class DeployPlan:
    """An ordered list of steps to execute on the remote host."""
    service_name: str
    steps: list[DeployStep] = field(default_factory=list)

    def add_step(self, description: str, command: str, critical: bool = True) -> None:
        self.steps.append(DeployStep(description, command, critical))

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        lines = [f"DeployPlan for '{self.service_name}' ({len(self.steps)} steps):"]
        for i, step in enumerate(self.steps, 1):
            flag = "[!]" if step.critical else "[ ]"
            lines.append(f"  {i}. {flag} {step.description}")
        return "\n".join(lines)


def plan_from_diff(diff: DiffResult, new_config: ServiceConfig) -> DeployPlan:
    """Generate a DeployPlan from a DiffResult and the target ServiceConfig."""
    plan = DeployPlan(service_name=diff.service_name)

    if not diff.has_changes:
        return plan

    env_changes = [c for c in diff.changes if c.key not in ('image', 'replicas')]
    image_changes = [c for c in diff.changes if c.key == 'image']
    replica_changes = [c for c in diff.changes if c.key == 'replicas']

    if image_changes:
        change = image_changes[0]
        plan.add_step(
            f"Pull new image: {change.new_value}",
            f"docker pull {change.new_value}",
        )

    if env_changes:
        env_args = " ".join(
            f"-e {c.key}={c.new_value}" for c in env_changes if c.change_type != 'removed'
        )
        plan.add_step(
            "Update environment variables",
            f"docker service update {env_args} {diff.service_name}",
        )

    if image_changes:
        plan.add_step(
            f"Update service image to {image_changes[0].new_value}",
            f"docker service update --image {image_changes[0].new_value} {diff.service_name}",
        )

    if replica_changes:
        change = replica_changes[0]
        plan.add_step(
            f"Scale replicas: {change.old_value} -> {change.new_value}",
            f"docker service scale {diff.service_name}={change.new_value}",
        )

    plan.add_step(
        "Verify service is running",
        f"docker service ls --filter name={diff.service_name}",
        critical=False,
    )

    return plan
