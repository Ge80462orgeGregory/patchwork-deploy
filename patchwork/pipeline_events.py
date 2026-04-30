"""Integration helpers: attach an EventBus to the deployment pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from patchwork.eventbus import EventBus, Event
from patchwork.executor import ExecutionReport, StepResult


# Standard topic names used by the pipeline integration.
TOPIC_DEPLOY_START = "deploy.start"
TOPIC_DEPLOY_STEP = "deploy.step"
TOPIC_DEPLOY_DONE = "deploy.done"
TOPIC_DEPLOY_FAILED = "deploy.failed"


@dataclass
class PipelineEventAdapter:
    """Publishes structured events from an ExecutionReport onto an EventBus."""

    bus: EventBus
    service: str = "unknown"
    _published: List[Event] = field(default_factory=list, init=False, repr=False)

    def on_start(self, step_count: int) -> None:
        e = self.bus.publish(TOPIC_DEPLOY_START, {
            "service": self.service,
            "step_count": step_count,
        })
        self._published.append(e)

    def on_step(self, result: StepResult) -> None:
        e = self.bus.publish(TOPIC_DEPLOY_STEP, {
            "service": self.service,
            "step": result.step.description,
            "success": result.ok,
            "output": result.output,
        })
        self._published.append(e)

    def on_done(self, report: ExecutionReport) -> None:
        topic = TOPIC_DEPLOY_DONE if report.success else TOPIC_DEPLOY_FAILED
        e = self.bus.publish(topic, {
            "service": self.service,
            "total": len(report.results),
            "failed": len(report.failed_steps),
        })
        self._published.append(e)

    def replay(self, report: ExecutionReport) -> None:
        """Convenience: emit start, each step, then done from a completed report."""
        self.on_start(len(report.results))
        for r in report.results:
            self.on_step(r)
        self.on_done(report)

    @property
    def published(self) -> List[Event]:
        return list(self._published)
