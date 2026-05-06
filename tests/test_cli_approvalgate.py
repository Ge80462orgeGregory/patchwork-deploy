"""Tests for patchwork.cli_approvalgate."""
import argparse
import pytest
from pathlib import Path

from patchwork.cli_approvalgate import build_approvalgate_parser, cmd_approvals
from patchwork.approvalgate import ApprovalGate


def _make_args(store: str, approval_cmd: str, **kwargs) -> argparse.Namespace:
    ns = argparse.Namespace(store=store, approval_cmd=approval_cmd)
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


@pytest.fixture
def store_file(tmp_path: Path) -> str:
    return str(tmp_path / "approvals.json")


class TestBuildParser:
    def test_returns_parser(self):
        root = argparse.ArgumentParser()
        sub = root.add_subparsers(dest="cmd")
        p = build_approvalgate_parser(sub)
        assert p is not None

    def test_approvals_subcommand_exists(self):
        root = argparse.ArgumentParser()
        sub = root.add_subparsers(dest="cmd")
        build_approvalgate_parser(sub)
        ns = root.parse_args(["approvals", "--store", "x.json", "list"])
        assert ns.approval_cmd == "list"

    def test_request_subcommand_captures_by(self):
        root = argparse.ArgumentParser()
        sub = root.add_subparsers(dest="cmd")
        build_approvalgate_parser(sub)
        ns = root.parse_args(["approvals", "request", "web", "--by", "alice"])
        assert ns.service == "web"
        assert ns.requested_by == "alice"

    def test_approve_subcommand_captures_by(self):
        root = argparse.ArgumentParser()
        sub = root.add_subparsers(dest="cmd")
        build_approvalgate_parser(sub)
        ns = root.parse_args(["approvals", "approve", "web", "--by", "carol"])
        assert ns.approved_by == "carol"


class TestCmdApprovals:
    def test_request_returns_zero(self, store_file, capsys):
        args = _make_args(store_file, "request", service="web", requested_by="alice")
        rc = cmd_approvals(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "web" in out
        assert "requested" in out

    def test_approve_returns_zero(self, store_file, capsys):
        gate = ApprovalGate(Path(store_file))
        gate.request("web", "alice")
        args = _make_args(store_file, "approve", service="web", approved_by="carol")
        rc = cmd_approvals(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "approved" in out

    def test_deny_returns_zero(self, store_file, capsys):
        gate = ApprovalGate(Path(store_file))
        gate.request("web", "alice")
        args = _make_args(store_file, "deny", service="web")
        rc = cmd_approvals(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "denied" in out

    def test_list_empty_store(self, store_file, capsys):
        args = _make_args(store_file, "list")
        rc = cmd_approvals(args)
        assert rc == 0
        assert "No approval" in capsys.readouterr().out

    def test_list_shows_entries(self, store_file, capsys):
        gate = ApprovalGate(Path(store_file))
        gate.request("api", "bob")
        args = _make_args(store_file, "list")
        cmd_approvals(args)
        out = capsys.readouterr().out
        assert "api" in out
        assert "PENDING" in out

    def test_duplicate_request_returns_one(self, store_file, capsys):
        gate = ApprovalGate(Path(store_file))
        gate.request("svc", "alice")
        args = _make_args(store_file, "request", service="svc", requested_by="bob")
        rc = cmd_approvals(args)
        assert rc == 1
        assert "error" in capsys.readouterr().err
