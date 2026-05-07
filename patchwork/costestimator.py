"""Cost estimator for deployment plans.

Assigns a cost score to each deploy step and aggregates totals
so operators can gate expensive rollouts before execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from patchwork.planner import DeployPlan, DeployStep


class CostError(Exception):
    """Raised when cost estimation fails."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"CostError({self.args[0]!r})"


# Default weights for step kinds
DEFAULT_WEIGHTS: Dict[str, float] = {
    "pull": 1.0,
    "stop": 0.5,
    "start": 1.5,
    "restart": 2.0,
    "scale": 1.0,
    "update_env": 0.5,
}


@dataclass
class CostEntry:
    service: str
    kind: str
    weight: float

    def to_dict(self) -> dict:
        return {"service": self.service, "kind": self.kind, "weight": self.weight}

    def __repr__(self) -> str:
        return f"CostEntry(service={self.service!r}, kind={self.kind!r}, weight={self.weight})"


@dataclass
class CostReport:
    entries: List[CostEntry] = field(default_factory=list)
    total: float = 0.0
    budget: float = 0.0

    @property
    def within_budget(self) -> bool:
        return self.budget <= 0 or self.total <= self.budget

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "total": self.total,
            "budget": self.budget,
            "within_budget": self.within_budget,
        }

    def summary(self) -> str:
        status = "OK" if self.within_budget else "OVER BUDGET"
        return f"Cost={self.total:.2f} Budget={self.budget:.2f} [{status}]"


class CostEstimator:
    """Estimates the cost of executing a DeployPlan."""

    def __init__(
        self,
        weights: Dict[str, float] | None = None,
        budget: float = 0.0,
    ) -> None:
        self._weights = weights if weights is not None else dict(DEFAULT_WEIGHTS)
        self._budget = budget

    def _weight_for(self, step: DeployStep) -> float:
        return self._weights.get(step.kind, 1.0)

    def estimate(self, plan: DeployPlan) -> CostReport:
        entries: List[CostEntry] = []
        total = 0.0
        for step in plan:
            w = self._weight_for(step)
            entries.append(CostEntry(service=step.service, kind=step.kind, weight=w))
            total += w
        return CostReport(entries=entries, total=round(total, 4), budget=self._budget)
