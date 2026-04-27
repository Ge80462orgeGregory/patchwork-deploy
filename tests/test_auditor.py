"""Tests for patchwork.auditor — AuditEntry and AuditLog."""

import json
from pathlib import Path

import pytest

from patchwork.auditor import AuditEntry, AuditLog


@pytest.fixture()
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "audit" / "deploy.log"


@pytest.fixture()
def audit_log(log_path: Path) -> AuditLog:
    return AuditLog(log_path)


class TestAuditEntry:
    def test_round_trip(self):
        entry = AuditEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            service="api",
            action="deploy",
            status="success",
            operator="alice",
            details="image updated",
        )
        restored = AuditEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.action == entry.action
        assert restored.status == entry.status
        assert restored.operator == entry.operator
        assert restored.details == entry.details

    def test_repr_contains_key_fields(self):
        entry = AuditEntry(
            timestamp="t", service="svc", action="rollback",
            status="failure", operator="bob"
        )
        r = repr(entry)
        assert "svc" in r
        assert "rollback" in r
        assert "failure" in r

    def test_missing_details_defaults_to_empty(self):
        data = {
            "timestamp": "t", "service": "svc", "action": "deploy",
            "status": "success", "operator": "alice"
        }
        entry = AuditEntry.from_dict(data)
        assert entry.details == ""


class TestAuditLog:
    def test_creates_parent_directory(self, log_path: Path):
        AuditLog(log_path)
        assert log_path.parent.exists()

    def test_record_writes_entry(self, audit_log: AuditLog, log_path: Path):
        audit_log.record("api", "deploy", "success", operator="alice")
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["service"] == "api"
        assert data["action"] == "deploy"
        assert data["status"] == "success"
        assert data["operator"] == "alice"

    def test_multiple_records_appended(self, audit_log: AuditLog):
        audit_log.record("api", "deploy", "success", operator="alice")
        audit_log.record("worker", "deploy", "failure", operator="bob")
        entries = audit_log.read_all()
        assert len(entries) == 2
        assert entries[0].service == "api"
        assert entries[1].service == "worker"

    def test_read_all_empty_when_no_file(self, log_path: Path):
        log = AuditLog(log_path)
        assert log.read_all() == []

    def test_read_service_filters_correctly(self, audit_log: AuditLog):
        audit_log.record("api", "deploy", "success", operator="alice")
        audit_log.record("worker", "deploy", "success", operator="alice")
        audit_log.record("api", "rollback", "success", operator="bob")
        api_entries = audit_log.read_service("api")
        assert len(api_entries) == 2
        assert all(e.service == "api" for e in api_entries)

    def test_record_returns_entry(self, audit_log: AuditLog):
        entry = audit_log.record("svc", "dry_run", "dry_run", operator="ci")
        assert isinstance(entry, AuditEntry)
        assert entry.service == "svc"
        assert entry.status == "dry_run"
