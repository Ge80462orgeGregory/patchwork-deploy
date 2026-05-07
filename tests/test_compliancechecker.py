"""Tests for patchwork.compliancechecker."""
import pytest

from patchwork.core import ServiceConfig
from patchwork.compliancechecker import (
    ComplianceChecker,
    ComplianceReport,
    ComplianceViolation,
)


def _make_config(
    name: str = "svc",
    image: str = "myapp:1.0.0",
    replicas: int = 2,
    env: dict = None,
) -> ServiceConfig:
    return ServiceConfig(
        name=name,
        image=image,
        replicas=replicas,
        env=env if env is not None else {"APP_ENV": "production"},
    )


@pytest.fixture
def checker() -> ComplianceChecker:
    return ComplianceChecker()


class TestComplianceViolation:
    def test_to_dict_contains_all_keys(self):
        v = ComplianceViolation(service="svc", rule="some-rule", detail="bad thing")
        d = v.to_dict()
        assert d["service"] == "svc"
        assert d["rule"] == "some-rule"
        assert d["detail"] == "bad thing"

    def test_repr_contains_service_and_rule(self):
        v = ComplianceViolation(service="svc", rule="min-replicas", detail="...")
        assert "svc" in repr(v)
        assert "min-replicas" in repr(v)


class TestComplianceReport:
    def test_compliant_when_no_violations(self):
        r = ComplianceReport()
        assert r.is_compliant is True

    def test_not_compliant_when_violations_present(self):
        r = ComplianceReport(
            violations=[ComplianceViolation("s", "r", "d")]
        )
        assert r.is_compliant is False

    def test_summary_compliant(self):
        assert "compliant" in ComplianceReport().summary.lower()

    def test_summary_shows_count(self):
        r = ComplianceReport(
            violations=[
                ComplianceViolation("s", "r", "d"),
                ComplianceViolation("s2", "r2", "d2"),
            ]
        )
        assert "2" in r.summary

    def test_to_dict_structure(self):
        r = ComplianceReport()
        d = r.to_dict()
        assert "compliant" in d
        assert "summary" in d
        assert "violations" in d
        assert d["violations"] == []


class TestComplianceChecker:
    def test_clean_config_passes(self, checker):
        cfg = _make_config()
        report = checker.check([cfg])
        assert report.is_compliant

    def test_latest_tag_triggers_violation(self, checker):
        cfg = _make_config(image="myapp:latest")
        report = checker.check([cfg])
        rules = [v.rule for v in report.violations]
        assert "no-banned-image-tags" in rules

    def test_image_without_tag_defaults_to_latest(self, checker):
        cfg = _make_config(image="myapp")
        report = checker.check([cfg])
        rules = [v.rule for v in report.violations]
        assert "no-banned-image-tags" in rules

    def test_dev_tag_triggers_violation(self, checker):
        cfg = _make_config(image="myapp:dev")
        report = checker.check([cfg])
        assert any(v.rule == "no-banned-image-tags" for v in report.violations)

    def test_zero_replicas_triggers_violation(self, checker):
        cfg = _make_config(replicas=0)
        report = checker.check([cfg])
        assert any(v.rule == "min-replicas" for v in report.violations)

    def test_missing_app_env_triggers_violation(self, checker):
        cfg = _make_config(env={})
        report = checker.check([cfg])
        assert any(v.rule == "required-env-keys" for v in report.violations)

    def test_multiple_configs_aggregated(self, checker):
        configs = [
            _make_config(name="ok"),
            _make_config(name="bad", image="myapp:latest", env={}),
        ]
        report = checker.check(configs)
        services = [v.service for v in report.violations]
        assert "bad" in services
        assert "ok" not in services

    def test_violation_detail_mentions_tag(self, checker):
        cfg = _make_config(image="myapp:debug")
        report = checker.check([cfg])
        v = next(v for v in report.violations if v.rule == "no-banned-image-tags")
        assert "debug" in v.detail
