"""Deployment reporting: formats and persists execution reports."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from patchwork.executor import ExecutionReport, StepResult


class ReportFormatter:
    """Formats an ExecutionReport into human-readable or JSON output."""

    def __init__(self, report: ExecutionReport) -> None:
        self.report = report

    def to_text(self) -> str:
        lines: list[str] = []
        r = self.report
        status = "SUCCESS" if r.success else "FAILED"
        lines.append(f"=== Deployment Report [{status}] ===")
        lines.append(f"Service : {r.service}")
        lines.append(f"Host    : {r.host}")
        lines.append(f"Steps   : {len(r.results)} total, "
                     f"{len(r.failed_steps)} failed")
        lines.append("")
        for step_result in r.results:
            icon = "✓" if step_result.success else "✗"
            lines.append(f"  {icon} [{step_result.step.action}] {step_result.step.description}")
            if step_result.output:
                for out_line in step_result.output.strip().splitlines():
                    lines.append(f"      {out_line}")
            if step_result.error:
                lines.append(f"      ERROR: {step_result.error}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        r = self.report
        return {
            "service": r.service,
            "host": r.host,
            "success": r.success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": [
                {
                    "action": sr.step.action,
                    "description": sr.step.description,
                    "success": sr.success,
                    "output": sr.output,
                    "error": sr.error,
                }
                for sr in r.results
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class ReportWriter:
    """Persists deployment reports to a directory."""

    def __init__(self, report_dir: str = "reports") -> None:
        self.report_dir = report_dir

    def write(self, report: ExecutionReport, fmt: str = "json") -> str:
        """Write report to file; returns the file path."""
        os.makedirs(self.report_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{report.service}_{ts}.{fmt}"
        path = os.path.join(self.report_dir, filename)
        formatter = ReportFormatter(report)
        content = formatter.to_json() if fmt == "json" else formatter.to_text()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path
