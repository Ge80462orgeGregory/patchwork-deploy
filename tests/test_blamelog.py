"""Tests for patchwork.blamelog."""
import json
from pathlib import Path

import pytest

from patchwork.blamelog import BlameEntry, BlameError, BlameLog


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "blame.json"


@pytest.fixture
def log(store_path: Path) -> BlameLog:
    return BlameLog(store_path)


class TestBlameEntry:
    def test_round_trip(self):
        entry = BlameEntry(
            entry_id="abc",
            service="api",
            actor="alice",
            reason="hotfix",
            triggered_at="2024-01-01T00:00:00+00:00",
            commit_sha="deadbeef",
            ticket="JIRA-42",
        )
        restored = BlameEntry.from_dict(entry.to_dict())
        assert restored.entry_id == entry.entry_id
        assert restored.service == entry.service
        assert restored.actor == entry.actor
        assert restored.commit_sha == entry.commit_sha
        assert restored.ticket == entry.ticket

    def test_optional_fields_default_to_none(self):
        entry = BlameEntry.from_dict({
            "entry_id": "x",
            "service": "svc",
            "actor": "bob",
            "reason": "routine",
            "triggered_at": "2024-01-01T00:00:00+00:00",
        })
        assert entry.commit_sha is None
        assert entry.ticket is None

    def test_repr_contains_key_fields(self):
        entry = BlameEntry("id", "svc", "alice", "deploy", "2024-01-01T00:00:00+00:00")
        r = repr(entry)
        assert "svc" in r
        assert "alice" in r
        assert "deploy" in r

    def test_blame_error_repr(self):
        err = BlameError("oops")
        assert "oops" in repr(err)


class TestBlameLog:
    def test_record_creates_entry(self, log: BlameLog):
        entry = log.record("api", "alice", "initial deploy")
        assert entry.service == "api"
        assert entry.actor == "alice"
        assert entry.reason == "initial deploy"
        assert entry.entry_id

    def test_record_persists_to_disk(self, log: BlameLog, store_path: Path):
        log.record("api", "alice", "test")
        raw = json.loads(store_path.read_text())
        assert len(raw) == 1
        assert raw[0]["service"] == "api"

    def test_for_service_filters_correctly(self, log: BlameLog):
        log.record("api", "alice", "deploy api")
        log.record("worker", "bob", "deploy worker")
        results = log.for_service("api")
        assert len(results) == 1
        assert results[0].service == "api"

    def test_all_entries_returns_all(self, log: BlameLog):
        log.record("api", "alice", "a")
        log.record("worker", "bob", "b")
        assert len(log.all_entries()) == 2

    def test_reload_from_disk(self, store_path: Path):
        log1 = BlameLog(store_path)
        log1.record("api", "alice", "deploy")
        log2 = BlameLog(store_path)
        assert len(log2.all_entries()) == 1
        assert log2.all_entries()[0].actor == "alice"

    def test_record_with_optional_fields(self, log: BlameLog):
        entry = log.record("api", "ci-bot", "automated",
                           commit_sha="abc123", ticket="OPS-7")
        assert entry.commit_sha == "abc123"
        assert entry.ticket == "OPS-7"
