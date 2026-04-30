"""Tests for patchwork.cli_circuitbreaker."""
import json
import argparse
import pytest

from patchwork.cli_circuitbreaker import (
    build_circuitbreaker_parser,
    cmd_circuit,
    _build_status,
    _print_text,
)
from patchwork.circuitbreaker import CircuitBreakerOptions, CircuitState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**kwargs):
    defaults = dict(
        services=["svc-a"],
        failure_threshold=3,
        recovery_timeout=30.0,
        format="text",
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestBuildParser:
    def setup_method(self):
        self.parser = argparse.ArgumentParser()
        self.sub = self.parser.add_subparsers()
        build_circuitbreaker_parser(self.sub)

    def test_parser_has_services_arg(self):
        ns = self.parser.parse_args(["circuit", "svc-a", "svc-b"])
        assert ns.services == ["svc-a", "svc-b"]

    def test_parser_defaults(self):
        ns = self.parser.parse_args(["circuit", "svc-a"])
        assert ns.failure_threshold == 3
        assert ns.recovery_timeout == 30.0
        assert ns.format == "text"

    def test_parser_custom_threshold(self):
        ns = self.parser.parse_args(["circuit", "svc-a", "--failure-threshold", "5"])
        assert ns.failure_threshold == 5


# ---------------------------------------------------------------------------
# _build_status
# ---------------------------------------------------------------------------

class TestBuildStatus:
    def test_returns_one_row_per_service(self):
        opts = CircuitBreakerOptions()
        rows = _build_status(["a", "b", "c"], opts)
        assert len(rows) == 3

    def test_new_circuit_is_closed_and_allowed(self):
        opts = CircuitBreakerOptions()
        rows = _build_status(["svc"], opts)
        assert rows[0]["state"] == CircuitState.CLOSED.value
        assert rows[0]["allow_request"] is True

    def test_service_name_in_row(self):
        opts = CircuitBreakerOptions()
        rows = _build_status(["my-service"], opts)
        assert rows[0]["service"] == "my-service"


# ---------------------------------------------------------------------------
# cmd_circuit output
# ---------------------------------------------------------------------------

class TestCmdCircuit:
    def test_text_output(self, capsys):
        args = _make_args(services=["alpha"], format="text")
        cmd_circuit(args)
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "closed" in out

    def test_json_output(self, capsys):
        args = _make_args(services=["beta"], format="json")
        cmd_circuit(args)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["service"] == "beta"

    def test_multiple_services_in_json(self, capsys):
        args = _make_args(services=["s1", "s2", "s3"], format="json")
        cmd_circuit(args)
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 3

    def test_print_text_no_allow(self, capsys):
        rows = [{"service": "x", "state": "open", "allow_request": False}]
        _print_text(rows)
        out = capsys.readouterr().out
        assert "allow=no" in out
