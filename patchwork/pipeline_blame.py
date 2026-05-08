"""Pipeline adapter that records blame entries on deployment completion."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from patchwork.blamelog import BlameEntry, BlameLog
from patchwork.executor import ExecutionReport


@dataclass
class BlameOptions:
    log_file: Path
    actor: str
    reason: str
    commit_sha: Optional[str] = None
    ticket: Optional[str] = None


@dataclass
class PipelineBlameAdapter:
    options: BlameOptions
    _recorded: list = field(default_factory=list, init=False)

    def record_report(self, report: ExecutionReport) -> list:
        """Record a blame entry for each service touched in *report*."""
        log = BlameLog(self.options.log_file)
        services = {step.step.service for step in report.steps if hasattr(step.step, "service")}
        entries: list[BlameEntry] = []
        for svc in sorted(services):
            entry = log.record(
                service=svc,
                actor=self.options.actor,
                reason=self.options.reason,
                commit_sha=self.options.commit_sha,
                ticket=self.options.ticket,
            )
            entries.append(entry)
        self._recorded.extend(entries)
        return entries

    def recorded(self) -> list:
        return list(self._recorded)
