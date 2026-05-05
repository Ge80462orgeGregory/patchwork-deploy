"""Drift detection: compare live service state against expected config."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from patchwork.core import ServiceConfig
from patchwork.ssh import SSHClient


@dataclass
class DriftEntry:
    service: str
    field: str
    expected: str
    actual: str

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"DriftEntry(service={self.service!r}, field={self.field!r}, "
            f"expected={self.expected!r}, actual={self.actual!r})"
        )

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class DriftReport:
    entries: List[DriftEntry] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return len(self.entries) > 0

    @property
    def summary(self) -> str:
        if not self.has_drift:
            return "No drift detected."
        lines = [f"Drift detected in {len(self.entries)} field(s):"]
        for e in self.entries:
            lines.append(f"  [{e.service}] {e.field}: expected={e.expected!r} actual={e.actual!r}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"has_drift": self.has_drift, "entries": [e.to_dict() for e in self.entries]}


class DriftDetector:
    """Query a remote host and compare running state to expected ServiceConfig."""

    def __init__(self, client: SSHClient) -> None:
        self._client = client

    def _run(self, cmd: str) -> Optional[str]:
        result = self._client.run(cmd)
        if result.ok:
            return result.stdout.strip()
        return None

    def check(self, config: ServiceConfig) -> DriftReport:
        report = DriftReport()
        svc = config.name

        # Check running image
        image_out = self._run(
            f"docker inspect --format '{{{{.Config.Image}}}}' {svc} 2>/dev/null"
        )
        if image_out is not None and image_out != config.image:
            report.entries.append(
                DriftEntry(service=svc, field="image", expected=config.image, actual=image_out)
            )

        # Check replica count via docker service ls (swarm)
        replicas_out = self._run(
            f"docker service ls --filter name={svc} --format '{{{{.Replicas}}}}' 2>/dev/null"
        )
        if replicas_out is not None:
            # Format: "2/2" — take the desired count
            parts = replicas_out.split("/")
            if len(parts) == 2:
                actual_replicas = parts[1].strip()
                expected_replicas = str(config.replicas)
                if actual_replicas != expected_replicas:
                    report.entries.append(
                        DriftEntry(
                            service=svc,
                            field="replicas",
                            expected=expected_replicas,
                            actual=actual_replicas,
                        )
                    )

        return report
