"""Compliance checker — validates deployed service configs against policy rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any

from patchwork.core import ServiceConfig


@dataclass
class ComplianceViolation:
    service: str
    rule: str
    detail: str

    def __repr__(self) -> str:
        return f"<ComplianceViolation service={self.service!r} rule={self.rule!r}>"

    def to_dict(self) -> Dict[str, str]:
        return {"service": self.service, "rule": self.rule, "detail": self.detail}


@dataclass
class ComplianceReport:
    violations: List[ComplianceViolation] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        return len(self.violations) == 0

    @property
    def summary(self) -> str:
        if self.is_compliant:
            return "All services are compliant."
        count = len(self.violations)
        return f"{count} compliance violation(s) found."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compliant": self.is_compliant,
            "summary": self.summary,
            "violations": [v.to_dict() for v in self.violations],
        }


class ComplianceChecker:
    """Checks a list of ServiceConfig objects against built-in policy rules."""

    # Minimum replica count required for production-like environments.
    MIN_REPLICAS: int = 1
    # Image tags that are explicitly disallowed.
    BANNED_TAGS: tuple = ("latest", "dev", "debug")

    def check(self, configs: List[ServiceConfig]) -> ComplianceReport:
        report = ComplianceReport()
        for cfg in configs:
            self._check_image_tag(cfg, report)
            self._check_replicas(cfg, report)
            self._check_required_env_keys(cfg, report)
        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_image_tag(self, cfg: ServiceConfig, report: ComplianceReport) -> None:
        tag = cfg.image.split(":")[-1] if ":" in cfg.image else "latest"
        if tag in self.BANNED_TAGS:
            report.violations.append(
                ComplianceViolation(
                    service=cfg.name,
                    rule="no-banned-image-tags",
                    detail=f"Image tag '{tag}' is not allowed in production.",
                )
            )

    def _check_replicas(self, cfg: ServiceConfig, report: ComplianceReport) -> None:
        if cfg.replicas < self.MIN_REPLICAS:
            report.violations.append(
                ComplianceViolation(
                    service=cfg.name,
                    rule="min-replicas",
                    detail=f"Replicas must be >= {self.MIN_REPLICAS}, got {cfg.replicas}.",
                )
            )

    def _check_required_env_keys(self, cfg: ServiceConfig, report: ComplianceReport) -> None:
        required = {"APP_ENV"}
        missing = required - set(cfg.env.keys())
        for key in sorted(missing):
            report.violations.append(
                ComplianceViolation(
                    service=cfg.name,
                    rule="required-env-keys",
                    detail=f"Required environment variable '{key}' is missing.",
                )
            )
