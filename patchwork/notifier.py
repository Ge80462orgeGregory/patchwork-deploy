"""Deployment notification system for patchwork-deploy.

Provides hooks to emit notifications (stdout, webhook, etc.) after
a deployment execution completes.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

from patchwork.executor import ExecutionReport


@dataclass
class NotificationResult:
    channel: str
    success: bool
    message: str

    def __repr__(self) -> str:  # pragma: no cover
        status = "ok" if self.success else "fail"
        return f"<NotificationResult channel={self.channel!r} status={status}>"


class Notifier:
    """Sends deployment outcome notifications over configured channels."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        timeout: int = 5,
    ) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify(self, report: ExecutionReport) -> List[NotificationResult]:
        """Dispatch notifications for *report* and return results."""
        results: List[NotificationResult] = []
        results.append(self._notify_stdout(report))
        if self.webhook_url:
            results.append(self._notify_webhook(report))
        return results

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def _notify_stdout(self, report: ExecutionReport) -> NotificationResult:
        status = "SUCCESS" if report.success else "FAILURE"
        failed = len(report.failed_steps)
        total = len(report.steps)
        msg = (
            f"[patchwork] Deployment {status} — "
            f"{total - failed}/{total} steps passed."
        )
        print(msg)
        return NotificationResult(channel="stdout", success=True, message=msg)

    def _notify_webhook(self, report: ExecutionReport) -> NotificationResult:
        payload = {
            "success": report.success,
            "total_steps": len(report.steps),
            "failed_steps": len(report.failed_steps),
            "duration_seconds": report.duration_seconds,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.webhook_url,  # type: ignore[arg-type]
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout):
                pass
            return NotificationResult(
                channel="webhook", success=True, message="Webhook delivered."
            )
        except Exception as exc:  # noqa: BLE001
            return NotificationResult(
                channel="webhook", success=False, message=str(exc)
            )
