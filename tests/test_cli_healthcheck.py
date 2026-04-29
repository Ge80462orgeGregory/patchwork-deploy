"""Tests for patchwork.cli_healthcheck."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from patchwork.cli_healthcheck import build_healthcheck_parser, cmd_healthcheck
from patchwork.healthcheck import HealthCheckResult


def _make_args(**kwargs):
    defaults = dict(
        services=["myapp"],
        host="10.0.0.1",
        user="root",
        port=22,
        key_path=None,
        retries=3,
        delay=0.0,
        command="systemctl is-active {service}",
        expected_output="active",
        output_format="text",
    )
    defaults.update(kwargs)
    ns = MagicMock()
    for k, v in defaults.items():
        setattr(ns, k, v)
    return ns


def _make_results(passed_map):
    return [
        HealthCheckResult(
            service=svc,
            passed=ok,
            attempts=1,
            message="ok" if ok else "fail",
            output="active" if ok else "",
        )
        for svc, ok in passed_map.items()
    ]


class TestBuildParser:
    def test_parser_has_services_arg(self):
        parser = build_healthcheck_parser()
        args = parser.parse_args(["svc-a", "--host", "1.2.3.4"])
        assert args.services == ["svc-a"]
        assert args.host == "1.2.3.4"

    def test_parser_defaults(self):
        parser = build_healthcheck_parser()
        args = parser.parse_args(["svc", "--host", "h"])
        assert args.retries == 3
        assert args.delay == 2.0
        assert args.output_format == "text"


class TestCmdHealthcheck:
    @patch("patchwork.cli_healthcheck.SSHClient")
    @patch("patchwork.cli_healthcheck.HealthChecker")
    def test_all_pass_returns_zero(self, MockChecker, MockSSH, capsys):
        instance = MockChecker.return_value
        instance.check_many.return_value = _make_results({"myapp": True})
        MockSSH.return_value.__enter__ = lambda s: MagicMock()
        MockSSH.return_value.__exit__ = MagicMock(return_value=False)

        args = _make_args(services=["myapp"], output_format="text")
        rc = cmd_healthcheck(args)
        assert rc == 0

    @patch("patchwork.cli_healthcheck.SSHClient")
    @patch("patchwork.cli_healthcheck.HealthChecker")
    def test_any_fail_returns_one(self, MockChecker, MockSSH, capsys):
        instance = MockChecker.return_value
        instance.check_many.return_value = _make_results({"svc-a": True, "svc-b": False})
        MockSSH.return_value.__enter__ = lambda s: MagicMock()
        MockSSH.return_value.__exit__ = MagicMock(return_value=False)

        args = _make_args(services=["svc-a", "svc-b"], output_format="text")
        rc = cmd_healthcheck(args)
        assert rc == 1

    @patch("patchwork.cli_healthcheck.SSHClient")
    @patch("patchwork.cli_healthcheck.HealthChecker")
    def test_json_output_is_valid(self, MockChecker, MockSSH, capsys):
        instance = MockChecker.return_value
        instance.check_many.return_value = _make_results({"api": True})
        MockSSH.return_value.__enter__ = lambda s: MagicMock()
        MockSSH.return_value.__exit__ = MagicMock(return_value=False)

        args = _make_args(services=["api"], output_format="json")
        cmd_healthcheck(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert data[0]["service"] == "api"
        assert data[0]["passed"] is True
