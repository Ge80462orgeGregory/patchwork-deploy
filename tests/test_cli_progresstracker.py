"""Tests for patchwork.cli_progresstracker."""
import json
import argparse
import pytest
from pathlib import Path

from patchwork.cli_progresstracker import build_progress_parser, cmd_progress


def _make_args(log_file: str, as_json: bool = False) -> argparse.Namespace:
    return argparse.Namespace(log_file=log_file, as_json=as_json)


def _write_log(path: Path, events: list) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events))


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
class TestBuildParser:
    def setup_method(self):
        self.root = argparse.ArgumentParser()
        self.sub = self.root.add_subparsers()
        build_progress_parser(self.sub)

    def test_parser_registers_progress_subcommand(self):
        args = self.root.parse_args(["progress", "run.log"])
        assert args.log_file == "run.log"

    def test_parser_json_flag_default_false(self):
        args = self.root.parse_args(["progress", "run.log"])
        assert args.as_json is False

    def test_parser_json_flag_enabled(self):
        args = self.root.parse_args(["progress", "run.log", "--json"])
        assert args.as_json is True


# ---------------------------------------------------------------------------
# cmd_progress
# ---------------------------------------------------------------------------
class TestCmdProgress:
    def _events(self):
        return [
            {"kind": "register", "service": "api", "total_steps": 2},
            {"kind": "step", "service": "api", "failed": False},
            {"kind": "step", "service": "api", "failed": False},
        ]

    def test_missing_file_returns_1(self, tmp_path):
        args = _make_args(str(tmp_path / "missing.log"))
        assert cmd_progress(args) == 1

    def test_valid_log_returns_0(self, tmp_path, capsys):
        p = tmp_path / "run.log"
        _write_log(p, self._events())
        args = _make_args(str(p))
        rc = cmd_progress(args)
        assert rc == 0

    def test_text_output_contains_service(self, tmp_path, capsys):
        p = tmp_path / "run.log"
        _write_log(p, self._events())
        cmd_progress(_make_args(str(p)))
        out = capsys.readouterr().out
        assert "api" in out
        assert "DONE" in out

    def test_json_output_is_valid(self, tmp_path, capsys):
        p = tmp_path / "run.log"
        _write_log(p, self._events())
        cmd_progress(_make_args(str(p), as_json=True))
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert data[0]["service"] == "api"
        assert data[0]["completed"] == 2
        assert data[0]["done"] is True

    def test_malformed_json_returns_2(self, tmp_path):
        p = tmp_path / "bad.log"
        p.write_text("{not valid json}\n")
        args = _make_args(str(p))
        assert cmd_progress(args) == 2

    def test_empty_log_returns_0(self, tmp_path, capsys):
        p = tmp_path / "empty.log"
        p.write_text("")
        assert cmd_progress(_make_args(str(p))) == 0
