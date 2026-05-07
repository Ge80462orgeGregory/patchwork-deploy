"""Tests for patchwork.cli_capacityplanner."""
import json
import argparse
import pytest

from patchwork.cli_capacityplanner import build_capacity_parser, cmd_capacity


def _make_args(config_file, limits=None, output_format="text"):
    ns = argparse.Namespace(
        config_file=str(config_file),
        limits=str(limits) if limits else None,
        output_format=output_format,
    )
    return ns


@pytest.fixture()
def config_file(tmp_path):
    data = [
        {"service": "web", "replicas": 3},
        {"service": "api", "replicas": 2},
    ]
    p = tmp_path / "configs.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture()
def limits_file(tmp_path):
    data = {
        "web": {"min_replicas": 1, "max_replicas": 5},
        "api": {"min_replicas": 1, "max_replicas": 4},
    }
    p = tmp_path / "limits.json"
    p.write_text(json.dumps(data))
    return p


class TestBuildParser:
    def test_returns_parser(self):
        p = build_capacity_parser()
        assert isinstance(p, argparse.ArgumentParser)

    def test_config_file_arg_exists(self):
        p = build_capacity_parser()
        parsed = p.parse_args(["some_file.json"])
        assert parsed.config_file == "some_file.json"

    def test_format_default_is_text(self):
        p = build_capacity_parser()
        parsed = p.parse_args(["f.json"])
        assert parsed.output_format == "text"

    def test_format_json_accepted(self):
        p = build_capacity_parser()
        parsed = p.parse_args(["f.json", "--format", "json"])
        assert parsed.output_format == "json"

    def test_limits_defaults_to_none(self):
        p = build_capacity_parser()
        parsed = p.parse_args(["f.json"])
        assert parsed.limits is None


class TestCmdCapacity:
    def test_ok_exit_code_when_no_violations(self, config_file, limits_file):
        args = _make_args(config_file, limits=limits_file)
        rc = cmd_capacity(args)
        assert rc == 0

    def test_nonzero_exit_when_violation(self, tmp_path, limits_file):
        data = [{"service": "web", "replicas": 99}]
        cf = tmp_path / "c.json"
        cf.write_text(json.dumps(data))
        args = _make_args(cf, limits=limits_file)
        rc = cmd_capacity(args)
        assert rc == 1

    def test_json_output_is_valid(self, config_file, limits_file, capsys):
        args = _make_args(config_file, limits=limits_file, output_format="json")
        cmd_capacity(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "entries" in parsed
        assert "has_violations" in parsed

    def test_text_output_contains_service(self, config_file, capsys):
        args = _make_args(config_file)
        cmd_capacity(args)
        out = capsys.readouterr().out
        assert "web" in out
        assert "api" in out

    def test_missing_config_file_returns_error(self, tmp_path):
        args = _make_args(tmp_path / "nonexistent.json")
        rc = cmd_capacity(args)
        assert rc == 1

    def test_invalid_limits_file_returns_error(self, config_file, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        args = _make_args(config_file, limits=bad)
        rc = cmd_capacity(args)
        assert rc == 1

    def test_no_limits_still_works(self, config_file):
        args = _make_args(config_file)
        rc = cmd_capacity(args)
        assert rc == 0
