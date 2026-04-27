"""Tests for patchwork.cli entry-point."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from patchwork.cli import main
from patchwork.executor import ExecutionReport, StepResult
from patchwork.planner import DeployStep
from patchwork.reporter import ReportWriter


def _write_sample_report(directory: str) -> str:
    """Helper: create a real JSON report file and return its path."""
    results = [
        StepResult(
            step=DeployStep(action="pull", description="pull image"),
            success=True,
            output="Pulled",
            error="",
        ),
        StepResult(
            step=DeployStep(action="restart", description="restart service"),
            success=False,
            output="",
            error="connection refused",
        ),
    ]
    report = ExecutionReport(service="api", host="10.0.0.1", results=results)
    writer = ReportWriter(report_dir=directory)
    return writer.write(report, fmt="json")


class TestCLIReport:
    def test_report_text_output(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_sample_report(tmpdir)
            rc = main(["report", path, "--format", "text"])
            assert rc == 0
            captured = capsys.readouterr()
            assert "api" in captured.out
            assert "10.0.0.1" in captured.out
            assert "FAILED" in captured.out

    def test_report_json_output(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_sample_report(tmpdir)
            rc = main(["report", path, "--format", "json"])
            assert rc == 0
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["service"] == "api"
            assert len(data["steps"]) == 2

    def test_report_missing_file(self, capsys):
        rc = main(["report", "/nonexistent/report.json"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_no_command_exits_zero(self, capsys):
        rc = main([])
        assert rc == 0
