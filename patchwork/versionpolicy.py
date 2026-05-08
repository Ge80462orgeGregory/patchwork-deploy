"""Version policy enforcement for service deployments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import re


class VersionPolicyError(Exception):
    """Raised when a version policy is misconfigured."""

    def __repr__(self) -> str:
        return f"VersionPolicyError({self.args[0]!r})"


@dataclass
class VersionViolation:
    service: str
    current: str
    candidate: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "current": self.current,
            "candidate": self.candidate,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"VersionViolation(service={self.service!r}, "
            f"current={self.current!r}, candidate={self.candidate!r})"
        )


@dataclass
class VersionPolicyReport:
    violations: List[VersionViolation] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        if self.is_compliant:
            return "All services comply with version policy."
        lines = [f"{len(self.violations)} version violation(s) found:"]
        for v in self.violations:
            lines.append(f"  [{v.service}] {v.reason}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "compliant": self.is_compliant,
            "violations": [v.to_dict() for v in self.violations],
        }


_SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[.-].+)?$"
)


def _parse_semver(version: str) -> Optional[tuple]:
    m = _SEMVER_RE.match(version)
    if not m:
        return None
    return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")))


@dataclass
class VersionPolicyChecker:
    """Checks that candidate versions respect configured policies."""

    allow_downgrades: bool = False
    require_semver: bool = True
    pinned_versions: dict = field(default_factory=dict)  # service -> exact version

    def __post_init__(self) -> None:
        if not isinstance(self.pinned_versions, dict):
            raise VersionPolicyError("pinned_versions must be a dict")

    def check(self, service: str, current: str, candidate: str) -> List[VersionViolation]:
        violations: List[VersionViolation] = []

        if self.require_semver:
            if _parse_semver(candidate) is None:
                violations.append(
                    VersionViolation(service, current, candidate,
                                     f"candidate {candidate!r} is not valid semver")
                )
                return violations  # further checks meaningless

        if service in self.pinned_versions:
            pinned = self.pinned_versions[service]
            if candidate != pinned:
                violations.append(
                    VersionViolation(service, current, candidate,
                                     f"service is pinned to {pinned!r}")
                )

        if not self.allow_downgrades and self.require_semver:
            cur_t = _parse_semver(current)
            cand_t = _parse_semver(candidate)
            if cur_t and cand_t and cand_t < cur_t:
                violations.append(
                    VersionViolation(service, current, candidate,
                                     f"downgrade from {current!r} to {candidate!r} is not allowed")
                )

        return violations

    def check_all(self, versions: dict) -> VersionPolicyReport:
        """versions: {service: {"current": str, "candidate": str}}"""
        report = VersionPolicyReport()
        for service, info in versions.items():
            report.violations.extend(
                self.check(service, info["current"], info["candidate"])
            )
        return report
