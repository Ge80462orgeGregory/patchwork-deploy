"""Tests for patchwork.reporter (ReportFormatter and ReportWriter)."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from patchwork.executor import ExecutionReport, StepResult
from patchwork.planner import DeployStep
from patchwork.reporter import ReportFormatter, ReportWriter


def _make_step(action: str, description: str) -> DeployStep:
    return DeployStep(action=action, description=description)


def _make_report(success_flags: list[bool]) -> ExecutionReport:
    results = []
    for i, ok in enumerate(success_flags):
        step = _make_step("run", f"step {i}")
        results.append(
            StepResult(
                step=step,
                success=ok,
                output=f"output {i}" if ok else "",
                error="" if ok else f"error {i}",
            )
        )
    return ExecutionReport(service="svc", host="host1", results=results)


class TestReportFormatter:
    def test_success_report_text(self):
        report = _make_report([True, True])
        text = ReportFormatter(report).to_text()
        assert "SUCCESS" in text
        assert "svc" in text
        assert "host1" in text
        assert "2 total" in text
        assert "0 failed" in text

    def test_failed_report_text(self):
        report = _make_report([True, False])
        text = ReportFormatter(report).to_text()
        assert "FAILED" in text
        assert "1 failed" in text
        assert "error 1" in text

    def test_to_dict_keys(self):
        report = _make_report([True])
        d = ReportFormatter(report).to_dict()
        assert set(d.keys()) == {"service", "host", "success", "timestamp", "steps"}
        assert d["success"] is True
        assert len(d["steps"]) == 1

    def test_to_json_valid(self):
        report = _make_report([True, False])
        raw = ReportFormatter(report).to_json()
        parsed = json.loads(raw)
        assert parsed["service"] == "svc"
        assert len(parsed["steps"]) == 2


class TestReportWriter:
    def test_write_json(self):
        report = _make_report([True])
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ReportWriter(report_dir=tmpdir)
            path = writer.write(report, fmt="json")
            assert os.path.exists(path)
            with open(path) as fh:
                data = json.load(fh)
            assert data["service"] == "svc"

    def test_write_text(self):
        report = _make_report([False])
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ReportWriter(report_dir=tmpdir)
            path = writer.write(report, fmt="txt")
            assert path.endswith(".txt")
            content = open(path).read()
            assert "FAILED" in content

    def test_creates_directory(self):
        report = _make_report([True])
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "deep", "reports")
            writer = ReportWriter(report_dir=nested)
            path = writer.write(report)
            assert os.path.isfile(path)
