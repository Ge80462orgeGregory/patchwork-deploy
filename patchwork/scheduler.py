"""Deployment scheduling: rate-limit and order deploy steps across services."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from patchwork.planner import DeployPlan, DeployStep


@dataclass
class SchedulerOptions:
    """Configuration for the deployment scheduler."""
    max_parallel: int = 1          # concurrent services (reserved for future async use)
    step_delay_seconds: float = 0.0  # pause between steps within a plan
    service_delay_seconds: float = 0.0  # pause between different services

    def __post_init__(self) -> None:
        if self.max_parallel < 1:
            raise ValueError("max_parallel must be >= 1")
        if self.step_delay_seconds < 0:
            raise ValueError("step_delay_seconds must be >= 0")
        if self.service_delay_seconds < 0:
            raise ValueError("service_delay_seconds must be >= 0")


@dataclass
class ScheduledBatch:
    """An ordered list of (service_name, plan) pairs ready for execution."""
    entries: List[tuple[str, DeployPlan]] = field(default_factory=list)

    def add(self, service_name: str, plan: DeployPlan) -> None:
        self.entries.append((service_name, plan))

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)


class Scheduler:
    """Orders and rate-limits deployment plans before execution."""

    def __init__(self, options: Optional[SchedulerOptions] = None) -> None:
        self.options = options or SchedulerOptions()

    def build_batch(
        self,
        plans: dict[str, DeployPlan],
        priority_order: Optional[List[str]] = None,
    ) -> ScheduledBatch:
        """Return a ScheduledBatch sorted by priority_order (then insertion order)."""
        batch = ScheduledBatch()
        ordered_keys: List[str]
        if priority_order:
            seen = set()
            ordered_keys = [k for k in priority_order if k in plans]
            seen.update(ordered_keys)
            ordered_keys += [k for k in plans if k not in seen]
        else:
            ordered_keys = list(plans.keys())

        for name in ordered_keys:
            batch.add(name, plans[name])
        return batch

    def iter_steps(
        self, batch: ScheduledBatch
    ):
        """Yield (service_name, step) with configured delays injected via sleep."""
        for svc_idx, (service_name, plan) in enumerate(batch):
            if svc_idx > 0 and self.options.service_delay_seconds > 0:
                time.sleep(self.options.service_delay_seconds)
            steps = list(plan.steps)
            for step_idx, step in enumerate(steps):
                if step_idx > 0 and self.options.step_delay_seconds > 0:
                    time.sleep(self.options.step_delay_seconds)
                yield service_name, step
