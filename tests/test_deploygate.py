"""Tests for patchwork.deploygate."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from patchwork.deploygate import DeployGate, GateResult, GateViolation


SERVICE = "api"
NOW = datetime(2024, 6, 15, 12, 0, 0)


def _gate(**kwargs) -> DeployGate:
    return DeployGate(**kwargs)


def _expired_lock():
    m = MagicMock()
    m.is_expired.return_value = True
    return m


def _active_lock(reason="manual hold"):
    m = MagicMock()
    m.is_expired.return_value = False
    m.reason = reason
    return m


# ---------------------------------------------------------------------------
# GateViolation
# ---------------------------------------------------------------------------

class TestGateViolation:
    def test_to_dict_contains_all_keys(self):
        v = GateViolation(service="svc", reason="locked", source="lock")
        d = v.to_dict()
        assert d["service"] == "svc"
        assert d["source"] == "lock"
        assert d["reason"] == "locked"

    def test_repr_contains_service_and_source(self):
        v = GateViolation(service="svc", reason="locked", source="lock")
        assert "svc" in repr(v)
        assert "lock" in repr(v)


# ---------------------------------------------------------------------------
# GateResult
# ---------------------------------------------------------------------------

class TestGateResult:
    def test_cleared_when_no_violations(self):
        r = GateResult(service=SERVICE)
        assert r.cleared is True

    def test_not_cleared_when_violation_added(self):
        r = GateResult(service=SERVICE)
        r.add_violation("lock", "held")
        assert r.cleared is False

    def test_to_dict_reflects_violations(self):
        r = GateResult(service=SERVICE)
        r.add_violation("maintenance", "in maintenance")
        d = r.to_dict()
        assert d["cleared"] is False
        assert len(d["violations"]) == 1
        assert d["violations"][0]["source"] == "maintenance"

    def test_repr_shows_cleared(self):
        r = GateResult(service=SERVICE)
        assert "CLEARED" in repr(r)

    def test_repr_shows_blocked_count(self):
        r = GateResult(service=SERVICE)
        r.add_violation("lock", "x")
        r.add_violation("approval", "y")
        assert "BLOCKED(2)" in repr(r)


# ---------------------------------------------------------------------------
# DeployGate.evaluate
# ---------------------------------------------------------------------------

class TestDeployGate:
    def test_no_providers_clears_service(self):
        gate = _gate()
        result = gate.evaluate(SERVICE, NOW)
        assert result.cleared is True

    def test_active_lock_blocks(self):
        lm = MagicMock()
        lm.get.return_value = _active_lock("freeze")
        gate = _gate(lock_manager=lm)
        result = gate.evaluate(SERVICE, NOW)
        assert not result.cleared
        assert result.violations[0].source == "lock"

    def test_expired_lock_does_not_block(self):
        lm = MagicMock()
        lm.get.return_value = _expired_lock()
        gate = _gate(lock_manager=lm)
        result = gate.evaluate(SERVICE, NOW)
        assert result.cleared is True

    def test_missing_lock_entry_does_not_block(self):
        lm = MagicMock()
        lm.get.return_value = None
        gate = _gate(lock_manager=lm)
        assert gate.evaluate(SERVICE, NOW).cleared is True

    def test_active_maintenance_blocks(self):
        ms = MagicMock()
        entry = MagicMock()
        entry.is_active.return_value = True
        ms.get.return_value = entry
        gate = _gate(maintenance_store=ms)
        result = gate.evaluate(SERVICE, NOW)
        assert not result.cleared
        assert result.violations[0].source == "maintenance"

    def test_unapproved_entry_blocks(self):
        ag = MagicMock()
        entry = MagicMock()
        entry.is_approved.return_value = False
        ag.get.return_value = entry
        gate = _gate(approval_gate=ag)
        result = gate.evaluate(SERVICE, NOW)
        assert not result.cleared
        assert result.violations[0].source == "approval"

    def test_outside_change_window_blocks(self):
        ws = MagicMock()
        window = MagicMock()
        window.allows.return_value = False
        ws.get.return_value = window
        gate = _gate(change_window_store=ws)
        result = gate.evaluate(SERVICE, NOW)
        assert not result.cleared
        assert result.violations[0].source == "change_window"

    def test_multiple_violations_accumulated(self):
        lm = MagicMock()
        lm.get.return_value = _active_lock()
        ms = MagicMock()
        entry = MagicMock()
        entry.is_active.return_value = True
        ms.get.return_value = entry
        gate = _gate(lock_manager=lm, maintenance_store=ms)
        result = gate.evaluate(SERVICE, NOW)
        assert len(result.violations) == 2

    def test_evaluate_many_returns_one_result_per_service(self):
        gate = _gate()
        results = gate.evaluate_many(["a", "b", "c"], NOW)
        assert len(results) == 3
        assert [r.service for r in results] == ["a", "b", "c"]
