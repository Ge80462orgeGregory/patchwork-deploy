"""Executes a DeployPlan against a remote host via SSH."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .planner import DeployPlan, DeployStep
from .ssh import SSHClient, SSHError

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    step: DeployStep
    success: bool
    output: str = ""
    error: Optional[str] = None

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"<StepResult [{status}] {self.step.description!r}>"


@dataclass
class ExecutionReport:
    host: str
    results: List[StepResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def failed_steps(self) -> List[StepResult]:
        return [r for r in self.results if not r.success]

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        return (
            f"Host {self.host}: {passed}/{total} steps succeeded"
            + (" — FAILED" if not self.success else " — OK")
        )


class PlanExecutor:
    """Runs each step in a DeployPlan over an SSH connection."""

    def __init__(self, client: SSHClient, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run

    def execute(self, plan: DeployPlan) -> ExecutionReport:
        report = ExecutionReport(host=self.client.host)

        if len(plan) == 0:
            logger.info("Plan is empty — nothing to execute on %s", self.client.host)
            return report

        for step in plan.steps:
            result = self._run_step(step)
            report.results.append(result)
            if not result.success and step.critical:
                logger.error(
                    "Critical step failed: %s — aborting plan", step.description
                )
                break

        return report

    def _run_step(self, step: DeployStep) -> StepResult:
        logger.info(
            "[%s] %s", "DRY-RUN" if self.dry_run else "EXEC", step.description
        )
        if self.dry_run:
            return StepResult(step=step, success=True, output="(dry-run)")

        try:
            cmd_result = self.client.run(step.command)
            success = cmd_result.ok
            return StepResult(
                step=step,
                success=success,
                output=cmd_result.stdout,
                error=cmd_result.stderr if not success else None,
            )
        except SSHError as exc:
            logger.exception("SSH error during step %r", step.description)
            return StepResult(step=step, success=False, error=str(exc))
