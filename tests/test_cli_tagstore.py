"""Tests for patchwork.cli_tagstore."""
import argparse
import json
import pytest
from pathlib import Path

from patchwork.cli_tagstore import build_tagstore_parser, cmd_tags, _parse_tags
from patchwork.tagstore import TagStore, DeploymentTag


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = {
        "tag_cmd": "put",
        "service": "svc-a",
        "deploy_id": "d001",
        "tags": ["env=prod"],
        "store": "",
        "as_json": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@pytest.fixture
def store_file(tmp_path) -> Path:
    return tmp_path / "tags.json"


class TestBuildParser:
    def test_parser_registers_tags_subcommand(self):
        root = argparse.ArgumentParser()
        sub = root.add_subparsers(dest="cmd")
        build_tagstore_parser(sub)
        args = root.parse_args(["tags", "put", "svc", "d1", "env=prod"])
        assert args.cmd == "tags"
        assert args.tag_cmd == "put"

    def test_parser_list_defaults(self):
        root = argparse.ArgumentParser()
        sub = root.add_subparsers(dest="cmd")
        build_tagstore_parser(sub)
        args = root.parse_args(["tags", "list", "svc-a"])
        assert args.as_json is False


class TestParseTagsHelper:
    def test_valid_tags(self):
        result = _parse_tags(["env=prod", "version=1.0"])
        assert result == {"env": "prod", "version": "1.0"}

    def test_invalid_tag_exits(self):
        with pytest.raises(SystemExit):
            _parse_tags(["badformat"])


class TestCmdTagsPut:
    def test_put_writes_record(self, store_file, capsys):
        args = _make_args(store=str(store_file))
        cmd_tags(args)
        store = TagStore(path=store_file)
        tag = store.get("svc-a", "d001")
        assert tag is not None
        assert tag.tags["env"] == "prod"

    def test_put_prints_confirmation(self, store_file, capsys):
        args = _make_args(store=str(store_file))
        cmd_tags(args)
        out = capsys.readouterr().out
        assert "svc-a" in out
        assert "d001" in out


class TestCmdTagsGet:
    def test_get_existing_text(self, store_file, capsys):
        store = TagStore(path=store_file)
        store.put(DeploymentTag("svc-a", "d001", {"env": "prod"}))
        args = _make_args(tag_cmd="get", store=str(store_file))
        cmd_tags(args)
        out = capsys.readouterr().out
        assert "env" in out
        assert "prod" in out

    def test_get_existing_json(self, store_file, capsys):
        store = TagStore(path=store_file)
        store.put(DeploymentTag("svc-a", "d001", {"env": "prod"}))
        args = _make_args(tag_cmd="get", store=str(store_file), as_json=True)
        cmd_tags(args)
        data = json.loads(capsys.readouterr().out)
        assert data["tags"]["env"] == "prod"

    def test_get_missing_exits(self, store_file):
        args = _make_args(tag_cmd="get", deploy_id="ghost", store=str(store_file))
        with pytest.raises(SystemExit):
            cmd_tags(args)


class TestCmdTagsDelete:
    def test_delete_removes_record(self, store_file, capsys):
        store = TagStore(path=store_file)
        store.put(DeploymentTag("svc-a", "d001", {"env": "prod"}))
        args = _make_args(tag_cmd="delete", store=str(store_file))
        cmd_tags(args)
        assert store.get("svc-a", "d001") is None

    def test_delete_missing_exits(self, store_file):
        args = _make_args(tag_cmd="delete", deploy_id="ghost", store=str(store_file))
        with pytest.raises(SystemExit):
            cmd_tags(args)
