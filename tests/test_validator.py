"""Tests for patchwork.validator module."""

import pytest
from patchwork.validator import validate_config, ValidationResult, ValidationError


def make_valid_config(**overrides):
    base = {
        "name": "web-service",
        "image": "nginx:1.25",
        "replicas": 2,
        "env": {"PORT": "8080"},
    }
    base.update(overrides)
    return base


class TestValidConfig:
    def test_valid_config_passes(self):
        result = validate_config(make_valid_config())
        assert result.valid
        assert result.errors == []

    def test_valid_summary_message(self):
        result = validate_config(make_valid_config())
        assert result.summary() == "Config is valid."

    def test_empty_env_is_valid(self):
        result = validate_config(make_valid_config(env={}))
        assert result.valid


class TestNameValidation:
    def test_missing_name(self):
        cfg = make_valid_config()
        del cfg["name"]
        result = validate_config(cfg)
        assert not result.valid
        fields = [e.field for e in result.errors]
        assert "name" in fields

    def test_empty_name(self):
        result = validate_config(make_valid_config(name=""))
        assert not result.valid

    def test_invalid_name_characters(self):
        result = validate_config(make_valid_config(name="my service!"))
        assert not result.valid
        assert any(e.field == "name" for e in result.errors)


class TestImageValidation:
    def test_missing_tag(self):
        result = validate_config(make_valid_config(image="nginx"))
        assert not result.valid
        assert any(e.field == "image" for e in result.errors)

    def test_empty_image(self):
        result = validate_config(make_valid_config(image=""))
        assert not result.valid

    def test_image_with_registry(self):
        result = validate_config(make_valid_config(image="registry.example.com/app:v2"))
        assert result.valid


class TestReplicasValidation:
    def test_zero_replicas(self):
        result = validate_config(make_valid_config(replicas=0))
        assert not result.valid

    def test_too_many_replicas(self):
        result = validate_config(make_valid_config(replicas=101))
        assert not result.valid

    def test_string_replicas(self):
        result = validate_config(make_valid_config(replicas="two"))
        assert not result.valid

    def test_max_valid_replicas(self):
        result = validate_config(make_valid_config(replicas=100))
        assert result.valid


class TestEnvValidation:
    def test_non_dict_env(self):
        result = validate_config(make_valid_config(env=["PORT=8080"]))
        assert not result.valid

    def test_non_string_value(self):
        result = validate_config(make_valid_config(env={"PORT": 8080}))
        assert not result.valid

    def test_summary_shows_all_errors(self):
        result = validate_config({"name": "", "image": "nginx", "replicas": -1})
        summary = result.summary()
        assert "Validation failed" in summary
        assert "name" in summary
