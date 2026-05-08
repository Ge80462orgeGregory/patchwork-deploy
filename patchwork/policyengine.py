"""Policy engine — evaluates named deployment policies against service configs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from patchwork.core import ServiceConfig


class PolicyError(Exception):
    """Raised for policy configuration problems."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"PolicyError({self.args[0]!r})"


@dataclass
class PolicyViolation:
    service: str
    policy: str
    reason: str

    def to_dict(self) -> dict:
        return {"service": self.service, "policy": self.policy, "reason": self.reason}

    def __repr__(self) -> str:
        return f"PolicyViolation(service={self.service!r}, policy={self.policy!r})"


@dataclass
class PolicyReport:
    violations: List[PolicyViolation] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        if self.is_compliant:
            return "All policies passed."
        lines = [f"  - [{v.policy}] {v.service}: {v.reason}" for v in self.violations]
        return "Policy violations:\n" + "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "compliant": self.is_compliant,
            "violations": [v.to_dict() for v in self.violations],
        }


# A policy rule is a callable: (ServiceConfig) -> Optional[str]
# Returns None when the config passes, or a reason string when it fails.
PolicyRule = Callable[[ServiceConfig], Optional[str]]


class PolicyEngine:
    """Holds named rules and evaluates them against one or more configs."""

    def __init__(self) -> None:
        self._rules: Dict[str, PolicyRule] = {}

    def register(self, name: str, rule: PolicyRule) -> None:
        if not name:
            raise PolicyError("Policy name must not be empty.")
        self._rules[name] = rule

    def evaluate(self, config: ServiceConfig) -> PolicyReport:
        report = PolicyReport()
        for policy_name, rule in self._rules.items():
            reason = rule(config)
            if reason is not None:
                report.violations.append(
                    PolicyViolation(
                        service=config.name,
                        policy=policy_name,
                        reason=reason,
                    )
                )
        return report

    def evaluate_all(self, configs: List[ServiceConfig]) -> PolicyReport:
        combined = PolicyReport()
        for cfg in configs:
            sub = self.evaluate(cfg)
            combined.violations.extend(sub.violations)
        return combined

    def __len__(self) -> int:
        return len(self._rules)
