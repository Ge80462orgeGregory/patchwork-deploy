"""Tests for patchwork.secrets — SecretMasker and MaskingResult."""
import pytest

from patchwork.secrets import SecretMasker, MaskingResult, _MASK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def masker() -> SecretMasker:
    return SecretMasker()


# ---------------------------------------------------------------------------
# MaskingResult
# ---------------------------------------------------------------------------

class TestMaskingResult:
    def test_stores_value_and_count(self):
        r = MaskingResult(value={"a": 1}, redacted_count=2)
        assert r.value == {"a": 1}
        assert r.redacted_count == 2

    def test_default_redacted_count_is_zero(self):
        r = MaskingResult(value="hello")
        assert r.redacted_count == 0


# ---------------------------------------------------------------------------
# SecretMasker.mask_dict
# ---------------------------------------------------------------------------

class TestMaskDict:
    def test_password_key_is_masked(self):
        result = masker().mask_dict({"password": "s3cr3t"})
        assert result.value["password"] == _MASK
        assert result.redacted_count == 1

    def test_token_key_is_masked(self):
        result = masker().mask_dict({"api_token": "abc123"})
        assert result.value["api_token"] == _MASK

    def test_non_secret_key_is_preserved(self):
        result = masker().mask_dict({"host": "example.com", "port": 22})
        assert result.value["host"] == "example.com"
        assert result.value["port"] == 22
        assert result.redacted_count == 0

    def test_nested_dict_secret_is_masked(self):
        data = {"db": {"password": "hunter2", "name": "mydb"}}
        result = masker().mask_dict(data)
        assert result.value["db"]["password"] == _MASK
        assert result.value["db"]["name"] == "mydb"
        assert result.redacted_count == 1

    def test_list_of_dicts(self):
        data = {"services": [{"secret": "x"}, {"name": "web"}]}
        result = masker().mask_dict(data)
        assert result.value["services"][0]["secret"] == _MASK
        assert result.value["services"][1]["name"] == "web"

    def test_original_dict_is_not_mutated(self):
        original = {"password": "real"}
        masker().mask_dict(original)
        assert original["password"] == "real"

    def test_multiple_secrets_counted(self):
        data = {"password": "a", "token": "b", "host": "c"}
        result = masker().mask_dict(data)
        assert result.redacted_count == 2


# ---------------------------------------------------------------------------
# SecretMasker.mask_string
# ---------------------------------------------------------------------------

class TestMaskString:
    def test_password_inline_masked(self):
        result = masker().mask_string("connect password=hunter2 host=db")
        assert _MASK in result.value
        assert "hunter2" not in result.value
        assert result.redacted_count == 1

    def test_non_secret_inline_preserved(self):
        result = masker().mask_string("host=localhost port=5432")
        assert "localhost" in result.value
        assert result.redacted_count == 0

    def test_token_env_var_masked(self):
        result = masker().mask_string("export API_TOKEN=abc123")
        assert "abc123" not in result.value
        assert result.redacted_count == 1


# ---------------------------------------------------------------------------
# Extra patterns
# ---------------------------------------------------------------------------

class TestExtraPatterns:
    def test_custom_key_pattern_masked(self):
        m = SecretMasker(extra_patterns=[r"passphrase"])
        result = m.mask_dict({"passphrase": "mypass"})
        assert result.value["passphrase"] == _MASK
