"""Tests for patchwork.cli_signalhandler."""
from __future__ import annotations

import argparse

import pytest

from patchwork.cli_signalhandler import build_signal_parser


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = {"tick": 1.0, "max_ticks": 0, "format": "text"}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestBuildParser:
    def test_returns_parser(self):
        p = build_signal_parser()
        assert isinstance(p, argparse.ArgumentParser)

    def test_tick_arg_exists(self):
        p = build_signal_parser()
        ns = p.parse_args(["--tick", "0.5"])
        assert ns.tick == pytest.approx(0.5)

    def test_max_ticks_arg_exists(self):
        p = build_signal_parser()
        ns = p.parse_args(["--max-ticks", "3"])
        assert ns.max_ticks == 3

    def test_format_arg_accepts_json(self):
        p = build_signal_parser()
        ns = p.parse_args(["--format", "json"])
        assert ns.format == "json"

    def test_format_arg_rejects_invalid(self):
        p = build_signal_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["--format", "yaml"])

    def test_defaults(self):
        p = build_signal_parser()
        ns = p.parse_args([])
        assert ns.tick == pytest.approx(1.0)
        assert ns.max_ticks == 0
        assert ns.format == "text"


class TestMakeArgs:
    """Sanity-check the helper used in other tests."""

    def test_override_tick(self):
        ns = _make_args(tick=0.25)
        assert ns.tick == pytest.approx(0.25)

    def test_override_format(self):
        ns = _make_args(format="json")
        assert ns.format == "json"

    def test_defaults_present(self):
        ns = _make_args()
        assert hasattr(ns, "max_ticks")
        assert hasattr(ns, "format")
