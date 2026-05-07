"""Tests for patchwork.cli_metricscollector."""
import json
import argparse
import pytest
from pathlib import Path
from patchwork.cli_metricscollector import build_metrics_parser, cmd_metrics


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = {"log_file": "metrics.json", "format": "text", "name_filter": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _write_log(path: Path, entries: list) -> None:
    path.write_text(json.dumps(entries))


class TestBuildParser:
    def test_returns_parser(self):
        p = build_metrics_parser()
        assert isinstance(p, argparse.ArgumentParser)

    def test_log_file_arg_exists(self):
        p = build_metrics_parser()
        ns = p.parse_args(["some_file.json"])
        assert ns.log_file == "some_file.json"

    def test_default_format_is_text(self):
        p = build_metrics_parser()
        ns = p.parse_args(["f.json"])
        assert ns.format == "text"

    def test_json_format_accepted(self):
        p = build_metrics_parser()
        ns = p.parse_args(["f.json", "--format", "json"])
        assert ns.format == "json"

    def test_filter_arg(self):
        p = build_metrics_parser()
        ns = p.parse_args(["f.json", "--filter", "deploy.ok"])
        assert ns.name_filter == "deploy.ok"


class TestCmdMetrics:
    def test_missing_file_returns_1(self, tmp_path):
        args = _make_args(log_file=str(tmp_path / "nope.json"))
        assert cmd_metrics(args) == 1

    def test_text_output_returns_0(self, tmp_path, capsys):
        f = tmp_path / "m.json"
        _write_log(f, [{"name": "deploy.ok", "value": 2.0, "labels": {}, "timestamp": 0.0}])
        args = _make_args(log_file=str(f))
        rc = cmd_metrics(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "deploy.ok" in out

    def test_json_output_is_valid_json(self, tmp_path, capsys):
        f = tmp_path / "m.json"
        _write_log(f, [{"name": "latency", "value": 120.0, "labels": {}, "timestamp": 1.0}])
        args = _make_args(log_file=str(f), format="json")
        rc = cmd_metrics(args)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data[0]["name"] == "latency"

    def test_filter_limits_output(self, tmp_path, capsys):
        f = tmp_path / "m.json"
        _write_log(f, [
            {"name": "deploy.ok", "value": 1.0, "labels": {}, "timestamp": 0.0},
            {"name": "deploy.fail", "value": 1.0, "labels": {}, "timestamp": 0.0},
        ])
        args = _make_args(log_file=str(f), name_filter="deploy.ok")
        cmd_metrics(args)
        out = capsys.readouterr().out
        assert "deploy.ok" in out
        assert "deploy.fail" not in out

    def test_empty_samples_prints_message(self, tmp_path, capsys):
        f = tmp_path / "m.json"
        _write_log(f, [])
        args = _make_args(log_file=str(f))
        rc = cmd_metrics(args)
        assert rc == 0
        assert "No metrics" in capsys.readouterr().out
