"""Tests for patchwork.policyengine."""
import pytest

from patchwork.core import ServiceConfig
from patchwork.policyengine import (
    PolicyEngine,
    PolicyError,
    PolicyReport,
    PolicyViolation,
)


def _make_config(name="svc", image="nginx:latest", replicas=2, env=None) -> ServiceConfig:
    return ServiceConfig(name=name, image=image, replicas=replicas, env=env or {})


# ---------------------------------------------------------------------------
# PolicyViolation
# ---------------------------------------------------------------------------

class TestPolicyViolation:
    def test_to_dict_contains_all_keys(self):
        v = PolicyViolation(service="svc", policy="min-replicas", reason="too few")
        d = v.to_dict()
        assert d["service"] == "svc"
        assert d["policy"] == "min-replicas"
        assert d["reason"] == "too few"

    def test_repr_contains_service_and_policy(self):
        v = PolicyViolation(service="svc", policy="min-replicas", reason="too few")
        assert "svc" in repr(v)
        assert "min-replicas" in repr(v)


# ---------------------------------------------------------------------------
# PolicyReport
# ---------------------------------------------------------------------------

class TestPolicyReport:
    def test_empty_report_is_compliant(self):
        assert PolicyReport().is_compliant

    def test_report_with_violation_is_not_compliant(self):
        r = PolicyReport(violations=[PolicyViolation("s", "p", "r")])
        assert not r.is_compliant

    def test_summary_passes(self):
        assert PolicyReport().summary() == "All policies passed."

    def test_summary_lists_violations(self):
        r = PolicyReport(violations=[PolicyViolation("svc", "min-replicas", "too few")])
        text = r.summary()
        assert "min-replicas" in text
        assert "svc" in text

    def test_to_dict_structure(self):
        r = PolicyReport(violations=[PolicyViolation("svc", "p", "reason")])
        d = r.to_dict()
        assert d["compliant"] is False
        assert len(d["violations"]) == 1


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class TestPolicyEngine:
    def _engine(self) -> PolicyEngine:
        return PolicyEngine()

    def test_empty_engine_has_zero_rules(self):
        assert len(self._engine()) == 0

    def test_register_increments_len(self):
        e = self._engine()
        e.register("no-latest", lambda c: None)
        assert len(e) == 1

    def test_empty_name_raises(self):
        with pytest.raises(PolicyError):
            self._engine().register("", lambda c: None)

    def test_passing_rule_yields_no_violations(self):
        e = self._engine()
        e.register("always-pass", lambda c: None)
        report = e.evaluate(_make_config())
        assert report.is_compliant

    def test_failing_rule_yields_violation(self):
        e = self._engine()
        e.register("no-latest", lambda c: "image tag is 'latest'" if c.image.endswith(":latest") else None)
        report = e.evaluate(_make_config(image="nginx:latest"))
        assert not report.is_compliant
        assert report.violations[0].policy == "no-latest"

    def test_multiple_rules_all_checked(self):
        e = self._engine()
        e.register("no-latest", lambda c: "latest tag" if ":latest" in c.image else None)
        e.register("min-replicas", lambda c: "need >= 2" if c.replicas < 2 else None)
        report = e.evaluate(_make_config(image="nginx:latest", replicas=1))
        assert len(report.violations) == 2

    def test_evaluate_all_aggregates_across_services(self):
        e = self._engine()
        e.register("min-replicas", lambda c: "need >= 2" if c.replicas < 2 else None)
        configs = [_make_config("a", replicas=1), _make_config("b", replicas=3)]
        report = e.evaluate_all(configs)
        assert len(report.violations) == 1
        assert report.violations[0].service == "a"
