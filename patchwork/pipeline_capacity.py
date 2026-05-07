"""Pipeline adapter that gates deployment if capacity violations exist."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from patchwork.capacityplanner import CapacityReport, evaluate_capacity


@dataclass
class CapacityGateOptions:
    """Options controlling how the capacity gate behaves inside a pipeline."""
    enabled: bool = True
    # If True, violations block the pipeline; if False, they are only logged.
    hard_block: bool = True
    limits: Optional[Dict[str, Dict]] = None


@dataclass
class CapacityGateResult:
    report: CapacityReport
    blocked: bool
    reason: str = ""

    @property
    def passed(self) -> bool:
        return not self.blocked

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "blocked": self.blocked,
            "reason": self.reason,
            "report": self.report.to_dict(),
        }

    def __repr__(self) -> str:
        state = "PASSED" if self.passed else "BLOCKED"
        return f"CapacityGateResult(state={state}, reason={self.reason!r})"


class PipelineCapacityAdapter:
    """Evaluates capacity before a pipeline proceeds.

    Usage::

        adapter = PipelineCapacityAdapter(options)
        result = adapter.evaluate(service_configs)
        if not result.passed:
            raise RuntimeError(result.reason)
    """

    def __init__(self, options: CapacityGateOptions | None = None) -> None:
        self.options = options or CapacityGateOptions()

    def evaluate(self, service_configs: List[Dict]) -> CapacityGateResult:
        """Run capacity check against *service_configs*.

        Returns a :class:`CapacityGateResult` indicating whether the pipeline
        should proceed.
        """
        if not self.options.enabled:
            empty = CapacityReport()
            return CapacityGateResult(report=empty, blocked=False, reason="capacity gate disabled")

        report = evaluate_capacity(service_configs, self.options.limits)

        if report.has_violations and self.options.hard_block:
            services = ", ".join(e.service for e in report.violations)
            reason = f"capacity violations detected for: {services}"
            return CapacityGateResult(report=report, blocked=True, reason=reason)

        reason = "" if not report.has_violations else "violations present (soft block only)"
        return CapacityGateResult(report=report, blocked=False, reason=reason)
