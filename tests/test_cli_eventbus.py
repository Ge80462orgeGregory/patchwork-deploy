"""Tests for patchwork.cli_eventbus."""
from __future__ import annotations

import json
import argparse
import pytest
from pathlib import Path

from patchwork.cli_eventbus import build_eventbus_parser, cmd_eventbus


def _write_events(path: Path, events: list) -> None:
    path.write_text(json.dumps(events))


def _make_args(log_file: str, topic: str | None = None, fmt: str = "text", limit: int = 0) -> argparse.Namespace:
    return argparse.Namespace(log_file=log_file, topic=topic, fmt=fmt, limit=limit)


class TestBuildParser:
    def test_parser_has_log_file_arg(self):
        parser = build_eventbus_parser()
        args = parser.parse_args(["events.json"])
        assert args.log_file == "events.json"

    def test_parser_defaults(self):
        parser = build_eventbus_parser()
        args = parser.parse_args(["f.json"])
        assert args.topic is None
        assert args.fmt == "text"
        assert args.limit == 0

    def test_parser_topic_flag(self):
        parser = build_eventbus_parser()
        args = parser.parse_args(["f.json", "--topic", "deploy.start"])
        assert args.topic == "deploy.start"


class TestCmdEventbus:
    def test_missing_file_returns_1(self, tmp_path):
        args = _make_args(str(tmp_path / "missing.json"))
        assert cmd_eventbus(args) == 1

    def test_invalid_json_returns_1(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json")
        args = _make_args(str(p))
        assert cmd_eventbus(args) == 1

    def test_non_list_json_returns_1(self, tmp_path):
        p = tmp_path / "obj.json"
        p.write_text(json.dumps({"topic": "x"}))
        args = _make_args(str(p))
        assert cmd_eventbus(args) == 1

    def test_text_output_success(self, tmp_path, capsys):
        p = tmp_path / "events.json"
        _write_events(p, [{"topic": "deploy.start", "payload": {}, "timestamp": "2024-01-01T00:00:00+00:00"}])
        args = _make_args(str(p))
        rc = cmd_eventbus(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "deploy.start" in out

    def test_json_output_success(self, tmp_path, capsys):
        p = tmp_path / "events.json"
        _write_events(p, [{"topic": "t", "payload": {"k": 1}, "timestamp": "2024-01-01T00:00:00+00:00"}])
        args = _make_args(str(p), fmt="json")
        rc = cmd_eventbus(args)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)

    def test_topic_filter(self, tmp_path, capsys):
        p = tmp_path / "events.json"
        _write_events(p, [
            {"topic": "a", "payload": {}, "timestamp": "2024-01-01T00:00:00+00:00"},
            {"topic": "b", "payload": {}, "timestamp": "2024-01-01T00:00:00+00:00"},
        ])
        args = _make_args(str(p), topic="a")
        cmd_eventbus(args)
        out = capsys.readouterr().out
        assert "topic=a" not in out  # text format
        assert out.count("[2024") == 1

    def test_limit_restricts_output(self, tmp_path, capsys):
        p = tmp_path / "events.json"
        events = [{"topic": "t", "payload": {}, "timestamp": "2024-01-01T00:00:00+00:00"} for _ in range(5)]
        _write_events(p, events)
        args = _make_args(str(p), limit=2)
        cmd_eventbus(args)
        out = capsys.readouterr().out
        assert out.count("[2024") == 2

    def test_empty_result_prints_message(self, tmp_path, capsys):
        p = tmp_path / "events.json"
        _write_events(p, [])
        args = _make_args(str(p))
        cmd_eventbus(args)
        assert "No events" in capsys.readouterr().out
