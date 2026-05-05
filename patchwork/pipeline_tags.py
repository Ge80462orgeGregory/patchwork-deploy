"""Pipeline adapter that auto-tags each completed deployment."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from patchwork.tagstore import DeploymentTag, TagStore
from patchwork.executor import ExecutionReport


@dataclass
class TaggingOptions:
    store_path: Path = Path(".patchwork/tags.json")
    extra_tags: Dict[str, str] = field(default_factory=dict)
    tag_failures: bool = True


class PipelineTagAdapter:
    """Attach deployment outcome tags to the TagStore after a pipeline run."""

    def __init__(self, options: TaggingOptions | None = None) -> None:
        self.options = options or TaggingOptions()
        self._store = TagStore(path=self.options.store_path)

    def record(self, service: str, deploy_id: str, report: ExecutionReport) -> DeploymentTag:
        """Build and persist a tag for a completed deployment."""
        outcome = "success" if report.success else "failure"
        tags: Dict[str, str] = {
            "outcome": outcome,
            "total_steps": str(len(report.results)),
            "failed_steps": str(len(report.failed_steps)),
        }
        tags.update(self.options.extra_tags)

        if not report.success and not self.options.tag_failures:
            # caller opted out of tagging failures
            return DeploymentTag(service=service, deploy_id=deploy_id, tags=tags)

        tag = DeploymentTag(service=service, deploy_id=deploy_id, tags=tags)
        self._store.put(tag)
        return tag

    def latest_outcome(self, service: str) -> str | None:
        """Return the outcome tag of the most recent deployment for *service*."""
        entries = self._store.list_for_service(service)
        if not entries:
            return None
        latest = max(entries, key=lambda e: e.created_at)
        return latest.tags.get("outcome")
