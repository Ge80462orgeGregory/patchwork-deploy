"""Tests for patchwork.pipeline_blame."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from patchwork.blamelog import BlameLog
from patchwork.pipeline_blame import BlameOptions, PipelineBlameAdapter


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "blame.json"


def _make_step_result(service: str) -> MagicMock:
    sr = MagicMock()
    sr.step.service = service
    return sr


def _make_report(*services: str) -> MagicMock:
    report = MagicMock()
    report.steps = [_make_step_result(s) for s in services]
    return report


class TestPipelineBlameAdapter:
    def test_records_entry_per_service(self, store_path: Path):
        opts = BlameOptions(log_file=store_path, actor="ci", reason="pipeline run")
        adapter = PipelineBlameAdapter(opts)
        report = _make_report("api", "worker")
        entries = adapter.record_report(report)
        assert len(entries) == 2
        services = {e.service for e in entries}
        assert services == {"api", "worker"}

    def test_deduplicates_services(self, store_path: Path):
        opts = BlameOptions(log_file=store_path, actor="ci", reason="retry")
        adapter = PipelineBlameAdapter(opts)
        report = _make_report("api", "api")
        entries = adapter.record_report(report)
        assert len(entries) == 1

    def test_persists_to_log(self, store_path: Path):
        opts = BlameOptions(log_file=store_path, actor="alice", reason="hotfix",
                            commit_sha="abc123", ticket="OPS-1")
        adapter = PipelineBlameAdapter(opts)
        adapter.record_report(_make_report("svc"))
        log = BlameLog(store_path)
        entries = log.for_service("svc")
        assert len(entries) == 1
        assert entries[0].actor == "alice"
        assert entries[0].commit_sha == "abc123"
        assert entries[0].ticket == "OPS-1"

    def test_recorded_accumulates_across_calls(self, store_path: Path):
        opts = BlameOptions(log_file=store_path, actor="bot", reason="auto")
        adapter = PipelineBlameAdapter(opts)
        adapter.record_report(_make_report("a"))
        adapter.record_report(_make_report("b"))
        assert len(adapter.recorded()) == 2

    def test_empty_report_records_nothing(self, store_path: Path):
        opts = BlameOptions(log_file=store_path, actor="ci", reason="empty")
        adapter = PipelineBlameAdapter(opts)
        entries = adapter.record_report(_make_report())
        assert entries == []
        assert not store_path.exists() or BlameLog(store_path).all_entries() == []
