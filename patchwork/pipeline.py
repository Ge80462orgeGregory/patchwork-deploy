"""pipeline.py — End-to-end deployment pipeline that wires together
loading, diffing, planning, executing, auditing, and notifying.

This module provides a single ``run_pipeline`` function that orchestrates
the full lifecycle of a patchwork deployment so that CLI commands and
programmatic callers share identical behaviour.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

from patchwork.loader import ConfigLoader
from patchwork.diff import diff_configs
from patchwork.planner import build_plan
from patchwork.executor import Executor, ExecutionReport
from patchwork.auditor import AuditLog, AuditEntry
from patchwork.notifier import Notifier
from patchwork.rollback import RollbackStore, Snapshot
from patchwork.reporter import ReportFormatter
from patchwork.ssh import SSHClient


@dataclass
class PipelineOptions:
    """Runtime knobs for a single pipeline run."""

    # Path to the desired-state config file
    config_path: str

    # SSH connection details
    host: str
    user: str
    ssh_key: Optional[str] = None

    # When True no commands are sent over SSH
    dry_run: bool = False

    # Optional paths for persistence; disabled when None
    audit_log_path: Optional[str] = None
    rollback_store_path: Optional[str] = None

    # Notification targets (passed straight to Notifier)
    notify_stdout: bool = True
    notify_webhook_url: Optional[str] = None


@dataclass
class PipelineResult:
    """Aggregated outcome of a full pipeline run."""

    report: ExecutionReport
    diff_summary: str
    audit_entry: Optional[AuditEntry] = None
    snapshot_saved: bool = False
    notifications_sent: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:  # noqa: D401
        """True when the execution report signals overall success."""
        return self.report.success


def run_pipeline(opts: PipelineOptions) -> PipelineResult:
    """Execute a full deployment pipeline and return a :class:`PipelineResult`.

    Steps
    -----
    1. Load & validate the config file.
    2. Diff against a stored snapshot (if any) to produce a :class:`DiffResult`.
    3. Build a :class:`DeployPlan` from the diff.
    4. Execute the plan (or simulate it when *dry_run* is True).
    5. Persist a new snapshot on success.
    6. Append an entry to the audit log.
    7. Dispatch notifications.
    """

    errors: list[str] = []

    # --- 1. Load config -------------------------------------------------------
    loader = ConfigLoader()
    config = loader.load(opts.config_path)

    # --- 2. Diff against previous snapshot ------------------------------------
    previous_config = None
    if opts.rollback_store_path:
        store = RollbackStore(opts.rollback_store_path)
        latest = store.latest(config.name)
        if latest:
            previous_config = latest.config

    diff_result = diff_configs(previous_config, config)
    diff_summary = diff_result.summary()

    # --- 3. Build plan --------------------------------------------------------
    plan = build_plan(diff_result)

    # --- 4. Execute -----------------------------------------------------------
    client = SSHClient(
        host=opts.host,
        user=opts.user,
        key_path=opts.ssh_key,
    )
    executor = Executor(client, dry_run=opts.dry_run)
    report = executor.run(plan)

    # --- 5. Save snapshot on success ------------------------------------------
    snapshot_saved = False
    if report.success and opts.rollback_store_path and not opts.dry_run:
        try:
            store = RollbackStore(opts.rollback_store_path)
            snapshot = Snapshot(
                service_name=config.name,
                config=config,
                taken_at=datetime.datetime.utcnow().isoformat(),
            )
            store.save(snapshot)
            snapshot_saved = True
        except Exception as exc:  # pragma: no cover
            errors.append(f"snapshot save failed: {exc}")

    # --- 6. Audit log ---------------------------------------------------------
    audit_entry: Optional[AuditEntry] = None
    if opts.audit_log_path:
        try:
            audit_log = AuditLog(opts.audit_log_path)
            formatter = ReportFormatter(report)
            audit_entry = AuditEntry(
                service=config.name,
                host=opts.host,
                dry_run=opts.dry_run,
                success=report.success,
                diff_summary=diff_summary,
                report_json=formatter.to_json(),
            )
            audit_log.append(audit_entry)
        except Exception as exc:  # pragma: no cover
            errors.append(f"audit log failed: {exc}")

    # --- 7. Notify ------------------------------------------------------------
    notifications_sent = 0
    try:
        notifier = Notifier(
            stdout=opts.notify_stdout,
            webhook_url=opts.notify_webhook_url,
        )
        result = notifier.notify(report)
        notifications_sent = result.sent
    except Exception as exc:  # pragma: no cover
        errors.append(f"notification failed: {exc}")

    return PipelineResult(
        report=report,
        diff_summary=diff_summary,
        audit_entry=audit_entry,
        snapshot_saved=snapshot_saved,
        notifications_sent=notifications_sent,
        errors=errors,
    )
