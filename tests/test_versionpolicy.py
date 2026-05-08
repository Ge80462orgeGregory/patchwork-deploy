"""Tests for patchwork.versionpolicy."""
import pytest

from patchwork.versionpolicy import (
    VersionPolicyChecker,
    VersionPolicyError,
    VersionPolicyReport,
    VersionViolation,
    _parse_semver,
)


# ---------------------------------------------------------------------------
# _parse_semver helpers
# ---------------------------------------------------------------------------

def test_parse_valid_semver():
    assert _parse_semver("1.2.3") == (1, 2, 3)


def test_parse_semver_with_suffix():
    assert _parse_semver("2.0.0-rc1") == (2, 0, 0)


def test_parse_invalid_semver_returns_none():
    assert _parse_semver("latest") is None
    assert _parse_semver("v1.2") is None


# ---------------------------------------------------------------------------
# VersionViolation
# ---------------------------------------------------------------------------

def test_violation_to_dict_contains_all_keys():
    v = VersionViolation("svc", "1.0.0", "0.9.0", "downgrade")
    d = v.to_dict()
    assert set(d.keys()) == {"service", "current", "candidate", "reason"}


def test_violation_repr_contains_service():
    v = VersionViolation("svc", "1.0.0", "0.9.0", "downgrade")
    assert "svc" in repr(v)


# ---------------------------------------------------------------------------
# VersionPolicyReport
# ---------------------------------------------------------------------------

def _make_report(n: int = 0) -> VersionPolicyReport:
    r = VersionPolicyReport()
    for i in range(n):
        r.violations.append(VersionViolation(f"svc{i}", "1.0.0", "0.9.0", "downgrade"))
    return r


def test_empty_report_is_compliant():
    assert _make_report(0).is_compliant


def test_report_with_violations_not_compliant():
    assert not _make_report(2).is_compliant


def test_summary_ok_message():
    assert "comply" in _make_report(0).summary()


def test_summary_lists_violations():
    s = _make_report(2).summary()
    assert "2 version violation" in s


def test_to_dict_structure():
    r = _make_report(1)
    d = r.to_dict()
    assert d["compliant"] is False
    assert len(d["violations"]) == 1


# ---------------------------------------------------------------------------
# VersionPolicyChecker
# ---------------------------------------------------------------------------

@pytest.fixture
def checker():
    return VersionPolicyChecker()


def test_valid_upgrade_no_violations(checker):
    v = checker.check("api", "1.0.0", "1.1.0")
    assert v == []


def test_downgrade_detected(checker):
    v = checker.check("api", "2.0.0", "1.9.9")
    assert len(v) == 1
    assert "downgrade" in v[0].reason


def test_allow_downgrades_flag():
    c = VersionPolicyChecker(allow_downgrades=True)
    assert c.check("api", "2.0.0", "1.0.0") == []


def test_non_semver_candidate_flagged(checker):
    v = checker.check("api", "1.0.0", "latest")
    assert any("semver" in x.reason for x in v)


def test_require_semver_false_allows_tags():
    c = VersionPolicyChecker(require_semver=False)
    assert c.check("api", "1.0.0", "latest") == []


def test_pinned_version_enforced():
    c = VersionPolicyChecker(pinned_versions={"api": "1.2.3"})
    v = c.check("api", "1.2.3", "1.3.0")
    assert any("pinned" in x.reason for x in v)


def test_pinned_version_exact_match_ok():
    c = VersionPolicyChecker(pinned_versions={"api": "1.2.3"})
    assert c.check("api", "1.2.2", "1.2.3") == []


def test_invalid_pinned_versions_raises():
    with pytest.raises(VersionPolicyError):
        VersionPolicyChecker(pinned_versions="bad")


def test_check_all_aggregates_violations():
    c = VersionPolicyChecker()
    versions = {
        "api": {"current": "2.0.0", "candidate": "1.9.0"},
        "worker": {"current": "1.0.0", "candidate": "1.1.0"},
    }
    report = c.check_all(versions)
    assert not report.is_compliant
    assert report.violations[0].service == "api"


def test_check_all_all_ok():
    c = VersionPolicyChecker()
    versions = {
        "api": {"current": "1.0.0", "candidate": "1.1.0"},
        "worker": {"current": "2.0.0", "candidate": "2.1.0"},
    }
    assert c.check_all(versions).is_compliant
