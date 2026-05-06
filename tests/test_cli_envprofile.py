"""Tests for patchwork.cli_envprofile."""
import argparse
import json
import pytest

from patchwork.cli_envprofile import build_profile_parser, cmd_profiles
from patchwork.envprofile import ProfileStore, EnvProfile


@pytest.fixture
def store_file(tmp_path):
    return str(tmp_path / "profiles.json")


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict(
        profiles_cmd=None,
        name=None,
        ssh_user="deploy",
        ssh_port=22,
        dry_run=False,
        env=[],
        allow=[],
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestBuildParser:
    def test_returns_parser(self):
        p = build_profile_parser()
        assert isinstance(p, argparse.ArgumentParser)

    def test_list_subcommand_exists(self):
        p = build_profile_parser()
        args = p.parse_args(["list"])
        assert args.profiles_cmd == "list"

    def test_set_subcommand_defaults(self):
        p = build_profile_parser()
        args = p.parse_args(["set", "dev"])
        assert args.name == "dev"
        assert args.ssh_user == "deploy"
        assert args.ssh_port == 22
        assert args.dry_run is False

    def test_delete_subcommand(self):
        p = build_profile_parser()
        args = p.parse_args(["delete", "staging"])
        assert args.profiles_cmd == "delete"
        assert args.name == "staging"


class TestCmdProfiles:
    def test_list_empty(self, store_file, capsys):
        rc = cmd_profiles(_make_args(profiles_cmd="list"), store_path=store_file)
        assert rc == 0
        out = capsys.readouterr().out
        assert "No profiles" in out

    def test_set_creates_profile(self, store_file, capsys):
        args = _make_args(profiles_cmd="set", name="dev", ssh_user="ci", env=[])
        rc = cmd_profiles(args, store_path=store_file)
        assert rc == 0
        store = ProfileStore(store_file)
        assert store.get("dev") is not None

    def test_set_with_env_vars(self, store_file):
        args = _make_args(
            profiles_cmd="set", name="prod",
            env=["LOG=warn", "DEBUG=false"],
        )
        cmd_profiles(args, store_path=store_file)
        p = ProfileStore(store_file).get("prod")
        assert p.env_vars == {"LOG": "warn", "DEBUG": "false"}

    def test_set_invalid_env_returns_error(self, store_file, capsys):
        args = _make_args(profiles_cmd="set", name="x", env=["BADVALUE"])
        rc = cmd_profiles(args, store_path=store_file)
        assert rc == 1

    def test_show_existing(self, store_file, capsys):
        s = ProfileStore(store_file)
        s.save(EnvProfile(name="staging"))
        rc = cmd_profiles(_make_args(profiles_cmd="show", name="staging"), store_path=store_file)
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["name"] == "staging"

    def test_show_missing_returns_error(self, store_file, capsys):
        rc = cmd_profiles(_make_args(profiles_cmd="show", name="ghost"), store_path=store_file)
        assert rc == 1

    def test_list_shows_profiles(self, store_file, capsys):
        s = ProfileStore(store_file)
        s.save(EnvProfile(name="dev"))
        s.save(EnvProfile(name="prod"))
        cmd_profiles(_make_args(profiles_cmd="list"), store_path=store_file)
        out = capsys.readouterr().out
        assert "dev" in out
        assert "prod" in out

    def test_delete_existing(self, store_file, capsys):
        s = ProfileStore(store_file)
        s.save(EnvProfile(name="tmp"))
        rc = cmd_profiles(_make_args(profiles_cmd="delete", name="tmp"), store_path=store_file)
        assert rc == 0
        assert ProfileStore(store_file).get("tmp") is None

    def test_delete_missing_returns_error(self, store_file):
        rc = cmd_profiles(_make_args(profiles_cmd="delete", name="nope"), store_path=store_file)
        assert rc == 1

    def test_no_subcommand_returns_error(self, store_file):
        rc = cmd_profiles(_make_args(profiles_cmd=None), store_path=store_file)
        assert rc == 1
