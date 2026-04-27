"""Tests for patchwork.loader module."""

import json
import pytest
from pathlib import Path

from patchwork.loader import ConfigLoader, LoadError
from patchwork.core import ServiceConfig


@pytest.fixture
def loader():
    return ConfigLoader()


@pytest.fixture
def tmp_json(tmp_path):
    def _write(data, filename="config.json"):
        p = tmp_path / filename
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)
    return _write


VALID_CONFIG = {
    "name": "api-service",
    "image": "myapp:v1.0",
    "replicas": 3,
    "env": {"DEBUG": "false"},
}


class TestLoadFile:
    def test_load_valid_json(self, loader, tmp_json):
        path = tmp_json(VALID_CONFIG)
        raw = loader.load_file(path)
        assert raw["name"] == "api-service"

    def test_missing_file_raises(self, loader):
        with pytest.raises(LoadError, match="not found"):
            loader.load_file("/nonexistent/path/config.json")

    def test_unsupported_extension_raises(self, loader, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text("[service]\nname = 'x'", encoding="utf-8")
        with pytest.raises(LoadError, match="Unsupported file format"):
            loader.load_file(str(p))

    def test_invalid_json_raises(self, loader, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json}", encoding="utf-8")
        with pytest.raises(LoadError, match="Failed to parse JSON"):
            loader.load_file(str(p))

    def test_non_mapping_json_raises(self, loader, tmp_path):
        p = tmp_path / "list.json"
        p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        with pytest.raises(LoadError, match="mapping"):
            loader.load_file(str(p))


class TestValidateAndBuild:
    def test_valid_config_returns_service_config(self, loader):
        config, result = loader.validate_and_build(VALID_CONFIG)
        assert result.valid
        assert isinstance(config, ServiceConfig)
        assert config.name == "api-service"

    def test_invalid_config_returns_none(self, loader):
        bad = {"name": "", "image": "nginx", "replicas": 0}
        config, result = loader.validate_and_build(bad)
        assert config is None
        assert not result.valid


class TestLoad:
    def test_load_returns_service_config(self, loader, tmp_json):
        path = tmp_json(VALID_CONFIG)
        config = loader.load(path)
        assert isinstance(config, ServiceConfig)
        assert config.replicas == 3

    def test_load_invalid_config_raises(self, loader, tmp_json):
        path = tmp_json({"name": "", "image": "nginx", "replicas": -1})
        with pytest.raises(LoadError, match="Invalid config"):
            loader.load(path)

    def test_load_missing_file_raises(self, loader):
        with pytest.raises(LoadError):
            loader.load("/does/not/exist.json")
