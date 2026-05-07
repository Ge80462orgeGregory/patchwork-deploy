"""Tests for patchwork.configtemplate."""
import pytest
from patchwork.configtemplate import ConfigTemplate, RenderResult, TemplateError


@pytest.fixture()
def tmpl() -> ConfigTemplate:
    return ConfigTemplate({"image": "nginx:1.25", "port": "8080", "env": "production"})


class TestRenderResult:
    def test_ok_when_no_missing(self):
        r = RenderResult(rendered={}, substitutions=2, missing=[])
        assert r.ok is True

    def test_not_ok_when_missing(self):
        r = RenderResult(rendered={}, substitutions=0, missing=["secret"])
        assert r.ok is False

    def test_repr_contains_key_fields(self):
        r = RenderResult(rendered={}, substitutions=3, missing=[])
        text = repr(r)
        assert "substitutions=3" in text
        assert "ok=True" in text


class TestConfigTemplate:
    def test_simple_substitution(self, tmpl):
        result = tmpl.render({"image": "{{ image }}", "port": "{{ port }}"})
        assert result.rendered == {"image": "nginx:1.25", "port": "8080"}
        assert result.substitutions == 2
        assert result.ok is True

    def test_missing_variable_recorded(self, tmpl):
        result = tmpl.render({"secret": "{{ db_password }}"})
        assert "db_password" in result.missing
        assert result.ok is False
        # placeholder kept intact
        assert "{{ db_password }}" in result.rendered["secret"]

    def test_nested_dict_substitution(self, tmpl):
        config = {"deploy": {"image": "{{ image }}", "replicas": 3}}
        result = tmpl.render(config)
        assert result.rendered["deploy"]["image"] == "nginx:1.25"
        assert result.substitutions == 1

    def test_list_values_substituted(self, tmpl):
        config = {"tags": ["{{ env }}", "stable"]}
        result = tmpl.render(config)
        assert result.rendered["tags"] == ["production", "stable"]

    def test_non_string_values_unchanged(self, tmpl):
        config = {"replicas": 5, "enabled": True}
        result = tmpl.render(config)
        assert result.rendered == {"replicas": 5, "enabled": True}
        assert result.substitutions == 0

    def test_set_adds_variable(self):
        t = ConfigTemplate()
        t.set("region", "us-east-1")
        result = t.render({"region": "{{ region }}"})
        assert result.rendered["region"] == "us-east-1"

    def test_update_bulk_adds_variables(self):
        t = ConfigTemplate()
        t.update({"a": "1", "b": "2"})
        result = t.render({"x": "{{ a }}-{{ b }}"})
        assert result.rendered["x"] == "1-2"
        assert result.substitutions == 2

    def test_duplicate_missing_deduplicated(self, tmpl):
        config = {"a": "{{ missing }}", "b": "{{ missing }}"}
        result = tmpl.render(config)
        assert result.missing.count("missing") == 1

    def test_render_json_valid(self, tmpl):
        raw = '{"image": "{{ image }}"}'
        result = tmpl.render_json(raw)
        assert result.rendered["image"] == "nginx:1.25"

    def test_render_json_invalid_raises(self, tmpl):
        with pytest.raises(TemplateError, match="Invalid JSON"):
            tmpl.render_json("{not valid json")

    def test_render_json_non_object_raises(self, tmpl):
        with pytest.raises(TemplateError, match="object"):
            tmpl.render_json('["a", "b"]')

    def test_whitespace_in_placeholder(self):
        t = ConfigTemplate({"key": "value"})
        result = t.render({"field": "{{  key  }}"})
        assert result.rendered["field"] == "value"
