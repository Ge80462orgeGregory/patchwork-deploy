"""Tests for patchwork.approvalgate."""
import time
import pytest
from pathlib import Path

from patchwork.approvalgate import ApprovalEntry, ApprovalGate, ApprovalError


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "approvals.json"


@pytest.fixture
def gate(store_path: Path) -> ApprovalGate:
    return ApprovalGate(store_path)


class TestApprovalEntry:
    def test_round_trip(self):
        entry = ApprovalEntry(service="web", requested_by="alice")
        restored = ApprovalEntry.from_dict(entry.to_dict())
        assert restored.service == entry.service
        assert restored.requested_by == entry.requested_by
        assert restored.approved_by == entry.approved_by
        assert restored.denied == entry.denied

    def test_is_pending_initially(self):
        entry = ApprovalEntry(service="web", requested_by="alice")
        assert entry.is_pending()
        assert not entry.is_approved()

    def test_repr_contains_key_fields(self):
        entry = ApprovalEntry(service="api", requested_by="bob")
        r = repr(entry)
        assert "api" in r
        assert "pending" in r

    def test_approved_entry_not_pending(self):
        entry = ApprovalEntry(
            service="db", requested_by="alice", approved_by="carol", approved_at=time.time()
        )
        assert entry.is_approved()
        assert not entry.is_pending()

    def test_denied_entry_not_approved(self):
        entry = ApprovalEntry(service="db", requested_by="alice", denied=True)
        assert not entry.is_approved()
        assert not entry.is_pending()


class TestApprovalGate:
    def test_request_creates_entry(self, gate):
        entry = gate.request("web", "alice")
        assert entry.service == "web"
        assert entry.is_pending()

    def test_approve_marks_approved(self, gate):
        gate.request("web", "alice")
        entry = gate.approve("web", "carol")
        assert entry.is_approved()
        assert entry.approved_by == "carol"
        assert entry.approved_at is not None

    def test_deny_marks_denied(self, gate):
        gate.request("web", "alice")
        entry = gate.deny("web")
        assert entry.denied
        assert not entry.is_approved()

    def test_is_approved_helper(self, gate):
        gate.request("web", "alice")
        assert not gate.is_approved("web")
        gate.approve("web", "carol")
        assert gate.is_approved("web")

    def test_duplicate_pending_request_raises(self, gate):
        gate.request("web", "alice")
        with pytest.raises(ApprovalError, match="already pending"):
            gate.request("web", "bob")

    def test_approve_missing_service_raises(self, gate):
        with pytest.raises(ApprovalError, match="No approval request"):
            gate.approve("ghost", "carol")

    def test_deny_missing_service_raises(self, gate):
        with pytest.raises(ApprovalError, match="No approval request"):
            gate.deny("ghost")

    def test_status_returns_none_for_unknown(self, gate):
        assert gate.status("unknown") is None

    def test_persistence_across_instances(self, store_path):
        g1 = ApprovalGate(store_path)
        g1.request("svc", "alice")
        g1.approve("svc", "carol")

        g2 = ApprovalGate(store_path)
        assert g2.is_approved("svc")

    def test_all_entries_returns_list(self, gate):
        gate.request("a", "alice")
        gate.request("b", "bob")
        entries = gate.all_entries()
        assert len(entries) == 2
        services = {e.service for e in entries}
        assert services == {"a", "b"}
