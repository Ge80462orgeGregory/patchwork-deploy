"""Tests for patchwork.driftdetector."""
from unittest.mock import MagicMock

import pytest

from patchwork.core import ServiceConfig
from patchwork.driftdetector import DriftDetector, DriftEntry, DriftReport
from patchwork.ssh import CommandResult


def _make_config(name="web", image="nginx:1.25", replicas=2) -> ServiceConfig:
    return ServiceConfig(name=name, image=image, replicas=replicas, env={})


def _cmd_ok(stdout: str) -> CommandResult:
    return CommandResult(stdout=stdout, stderr="", exit_code=0)


def _cmd_fail() -> CommandResult:
    return CommandResult(stdout="", stderr="error", exit_code=1)


def _make_client(image_out=None, replicas_out=None):
    client = MagicMock()
    responses = []
    if image_out is not None:
        responses.append(_cmd_ok(image_out))
    else:
        responses.append(_cmd_fail())
    if replicas_out is not None:
        responses.append(_cmd_ok(replicas_out))
    else:
        responses.append(_cmd_fail())
    client.run.side_effect = responses
    return client


class TestDriftEntry:
    def test_to_dict_has_all_keys(self):
        e = DriftEntry(service="svc", field="image", expected="a", actual="b")
        d = e.to_dict()
        assert d == {"service": "svc", "field": "image", "expected": "a", "actual": "b"}


class TestDriftReport:
    def test_no_drift_when_empty(self):
        r = DriftReport()
        assert not r.has_drift
        assert r.summary == "No drift detected."

    def test_has_drift_when_entries_present(self):
        r = DriftReport(entries=[DriftEntry("svc", "image", "a", "b")])
        assert r.has_drift
        assert "Drift detected" in r.summary

    def test_to_dict_structure(self):
        r = DriftReport(entries=[DriftEntry("svc", "image", "a", "b")])
        d = r.to_dict()
        assert d["has_drift"] is True
        assert len(d["entries"]) == 1


class TestDriftDetector:
    def test_no_drift_when_state_matches(self):
        config = _make_config(image="nginx:1.25", replicas=2)
        client = _make_client(image_out="nginx:1.25", replicas_out="2/2")
        detector = DriftDetector(client)
        report = detector.check(config)
        assert not report.has_drift

    def test_image_drift_detected(self):
        config = _make_config(image="nginx:1.25", replicas=2)
        client = _make_client(image_out="nginx:1.24", replicas_out="2/2")
        detector = DriftDetector(client)
        report = detector.check(config)
        assert report.has_drift
        assert any(e.field == "image" for e in report.entries)

    def test_replica_drift_detected(self):
        config = _make_config(image="nginx:1.25", replicas=3)
        client = _make_client(image_out="nginx:1.25", replicas_out="1/1")
        detector = DriftDetector(client)
        report = detector.check(config)
        assert report.has_drift
        assert any(e.field == "replicas" for e in report.entries)

    def test_both_drifts_detected(self):
        config = _make_config(image="nginx:1.25", replicas=3)
        client = _make_client(image_out="nginx:1.24", replicas_out="1/1")
        detector = DriftDetector(client)
        report = detector.check(config)
        assert len(report.entries) == 2

    def test_skips_field_when_command_fails(self):
        config = _make_config(image="nginx:1.25", replicas=2)
        client = _make_client(image_out=None, replicas_out=None)
        detector = DriftDetector(client)
        report = detector.check(config)
        assert not report.has_drift

    def test_summary_lists_all_drifts(self):
        config = _make_config(image="nginx:1.25", replicas=3)
        client = _make_client(image_out="nginx:1.24", replicas_out="1/1")
        detector = DriftDetector(client)
        report = detector.check(config)
        summary = report.summary
        assert "image" in summary
        assert "replicas" in summary
