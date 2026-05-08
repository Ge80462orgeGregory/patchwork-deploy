"""Tests for patchwork.cli_canarymanager."""
import json
import argparse
import pytest
from pathlib import Path
from patchwork.cli_canarymanager import build_canary_parser, cmd_canary
from patchwork.canarymanager import CanaryManager


def _make_args(store: str, subcommand: str, **kwargs) -> argparse.Namespace:
    defaults = {"store": store, "subcommand": subcommand, "as_json": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@pytest.fixture
def store_file(tmp_path: Path) -> str:
    return str(tmp_path / "canary.json")


class TestBuildParser:
    def test_returns_parser(self):
        assert isinstance(build_canary_parser(), argparse.ArgumentParser)

    def test_create_subcommand_exists(self):
        p = build_canary_parser()
        args = p.parse_args(["--store", "x.json", "create", "api", "--weight", "20"])
        assert args.subcommand == "create"
        assert args.service == "api"
        assert args.weight == 20

    def test_promote_subcommand_exists(self):
        p = build_canary_parser()
        args = p.parse_args(["promote", "api"])
        assert args.subcommand == "promote"

    def test_abort_subcommand_exists(self):
        p = build_canary_parser()
        args = p.parse_args(["abort", "api"])
        assert args.subcommand == "abort"

    def test_list_defaults_no_json(self):
        p = build_canary_parser()
        args = p.parse_args(["list"])
        assert args.as_json is False

    def test_list_json_flag(self):
        p = build_canary_parser()
        args = p.parse_args(["list", "--json"])
        assert args.as_json is True


class TestCmdCanary:
    def test_create_returns_zero(self, store_file, capsys):
        args = _make_args(store_file, "create", service="api", weight=10)
        rc = cmd_canary(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "api" in out

    def test_promote_returns_zero(self, store_file, capsys):
        CanaryManager(store_path=store_file).create("api", 10)
        args = _make_args(store_file, "promote", service="api")
        rc = cmd_canary(args)
        assert rc == 0
        assert "Promoted" in capsys.readouterr().out

    def test_abort_returns_zero(self, store_file, capsys):
        CanaryManager(store_path=store_file).create("api", 10)
        args = _make_args(store_file, "abort", service="api")
        rc = cmd_canary(args)
        assert rc == 0
        assert "Aborted" in capsys.readouterr().out

    def test_list_text_empty(self, store_file, capsys):
        args = _make_args(store_file, "list")
        rc = cmd_canary(args)
        assert rc == 0
        assert "No active" in capsys.readouterr().out

    def test_list_json_output(self, store_file, capsys):
        CanaryManager(store_path=store_file).create("api", 15)
        args = _make_args(store_file, "list", as_json=True)
        cmd_canary(args)
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["service"] == "api"

    def test_duplicate_create_returns_one(self, store_file, capsys):
        CanaryManager(store_path=store_file).create("api", 10)
        args = _make_args(store_file, "create", service="api", weight=20)
        rc = cmd_canary(args)
        assert rc == 1
        assert "error" in capsys.readouterr().out

    def test_promote_unknown_returns_one(self, store_file, capsys):
        args = _make_args(store_file, "promote", service="ghost")
        rc = cmd_canary(args)
        assert rc == 1
